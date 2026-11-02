from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.sites import site
from django.contrib.auth.models import User, Permission
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from expenses.models import (
    OperatingExpense, UpcomingExpensePayment, UpcomingExpensePlan, UpcomingExpenseType,
)
from expenses.upcoming_services import ensure_installment, materialize_monthly_payments, monthly_date, set_payment_paid


class ExpensePlannerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("expense_owner", "owner@example.test", "test")
        self.client.force_login(self.user)
        self.url = reverse("expense_planner")
        self.type = UpcomingExpenseType.objects.create(name="Office rent test")
        self.today = date(2026, 11, 2)
        self.clock = patch("tasks.expense_planner_views.timezone.localdate", return_value=self.today)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def plan(self, **overrides):
        data = {
            "payment_type": self.type, "description": "Office rent",
            "amount": Decimal("100.00"), "start_date": date(2026, 11, 10),
            "frequency": "once", "created_by": self.user,
        }
        data.update(overrides)
        plan = UpcomingExpensePlan.objects.create(**data)
        ensure_installment(plan, plan.start_date)
        return plan

    def test_page_and_every_post_action_are_superuser_only(self):
        for staff in (False, True):
            user = User.objects.create_user(username=f"staff_{staff}", is_staff=staff)
            user.user_permissions.set(Permission.objects.filter(content_type__app_label="expenses"))
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            for action in ("create", "create_type", "paid", "edit", "stop", "partial", "delete", "delete_plan", "edit_plan"):
                response = self.client.post(self.url, {"action": action})
                self.assertEqual(response.status_code, 403)
        self.assertFalse(UpcomingExpensePlan.objects.exists())
        self.assertFalse(UpcomingExpensePayment.objects.exists())

    def test_anonymous_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_nav_link_hidden_from_staff_and_visible_to_superuser(self):
        response = self.client.get(reverse("current_lead_tasks"))
        self.assertContains(response, self.url)
        staff = User.objects.create_user(username="menu_staff", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("current_lead_tasks"))
        self.assertNotContains(response, self.url)

    def test_create_once_payment_is_not_accounting_expense(self):
        response = self.client.post(self.url, {
            "action": "create", "payment_type": self.type.pk,
            "description": "Internet renewal", "amount": "79.95",
            "start_date": "2026-11-15", "frequency": "once",
        })
        self.assertEqual(response.status_code, 302)
        payment = UpcomingExpensePayment.objects.get()
        self.assertEqual(payment.amount, Decimal("79.95"))
        self.assertEqual(payment.description, "Internet renewal")
        self.assertEqual(payment.due_date, date(2026, 11, 15))
        self.assertFalse(payment.is_paid)
        self.assertEqual(payment.plan.created_by, self.user)
        self.assertFalse(OperatingExpense.objects.exists())

    def test_mark_paid_deducts_balance_hides_row_and_records_history(self):
        first = self.plan().payments.get()
        other = self.plan(amount=Decimal("65.25")).payments.get()
        response = self.client.post(self.url, {
            "action": "paid", "payment_id": first.pk, "paid": "yes",
        })
        self.assertEqual(response.status_code, 302)
        first.refresh_from_db()
        self.assertTrue(first.is_paid)
        self.assertEqual(first.paid_by, self.user)
        self.assertIsNotNone(first.paid_at)
        page = self.client.get(self.url)
        self.assertEqual(page.context["totals"]["outstanding"], Decimal("65.25"))
        self.assertEqual([p.pk for p in page.context["page"]], [other.pk])
        history = self.client.get(self.url, {"status": "paid"})
        self.assertEqual([p.pk for p in history.context["page"]], [first.pk])
        self.assertEqual(history.context["totals"]["paid_total"], Decimal("100"))
        self.client.post(self.url, {"action": "paid", "payment_id": first.pk, "paid": "no"})
        first.refresh_from_db()
        self.assertFalse(first.is_paid)
        self.assertIsNone(first.paid_at)
        self.assertIsNone(first.paid_by)

    def test_monthly_payments_accumulate_even_when_previous_unpaid(self):
        plan = self.plan(frequency="monthly", start_date=date(2026, 9, 10))
        materialize_monthly_payments(self.today)
        materialize_monthly_payments(self.today)
        self.assertEqual(list(plan.payments.values_list("scheduled_for", flat=True)), [
            date(2026, 9, 10), date(2026, 10, 10), date(2026, 11, 10),
        ])
        page = self.client.get(self.url)
        self.assertEqual(page.context["totals"]["outstanding"], Decimal("300"))
        self.assertEqual(page.context["totals"]["overdue_total"], Decimal("200"))
        payment = plan.payments.first()
        set_payment_paid(payment.pk, True, self.user)
        page = self.client.get(self.url)
        self.assertEqual(page.context["totals"]["outstanding"], Decimal("200"))
        self.assertEqual(plan.payments.count(), 3)  # Paying does not add another month early.
        self.assertEqual(plan.payments.filter(is_paid=False).count(), 2)
        materialize_monthly_payments(date(2026, 12, 1))
        self.assertEqual(plan.payments.count(), 4)

    def test_month_end_recurring_dates_do_not_drift(self):
        start = date(2027, 1, 31)
        self.assertEqual(monthly_date(start, 1), date(2027, 2, 28))
        self.assertEqual(monthly_date(start, 2), date(2027, 3, 31))
        self.assertEqual(monthly_date(date(2028, 1, 31), 1), date(2028, 2, 29))

    def test_future_first_payment_visible_without_creating_more_months(self):
        plan = self.plan(frequency="monthly", start_date=date(2027, 2, 15))
        self.client.get(self.url)
        self.assertEqual(plan.payments.count(), 1)

    def test_filters_and_totals_use_same_rows(self):
        wanted = self.plan(description="Internet bill", amount=Decimal("12.34")).payments.get()
        self.plan(description="Power bill", amount=Decimal("56.78"))
        self.plan(description="Internet older", start_date=date(2026, 9, 1))
        response = self.client.get(self.url, {
            "payment_type": self.type.pk, "search": "Internet",
            "due_from": "2026-11-01", "due_to": "2026-11-30",
            "status": "unpaid", "repeat": "once", "sort": "-due",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["totals"]["outstanding"], Decimal("12.34"))
        self.assertEqual([p.pk for p in response.context["page"]], [wanted.pk])

    def test_overdue_filter_and_amount_sort(self):
        older = self.plan(start_date=date(2026, 10, 10), amount=Decimal("25")).payments.get()
        newer = self.plan(start_date=date(2026, 10, 11), amount=Decimal("50")).payments.get()
        self.plan(start_date=date(2026, 11, 10))
        response = self.client.get(self.url, {"overdue": "on", "sort": "amount"})
        self.assertEqual([p.pk for p in response.context["page"]], [newer.pk, older.pk])
        self.assertEqual(response.context["totals"]["overdue_total"], Decimal("75"))

    def test_totals_cover_all_pages_and_decimal_amounts(self):
        plan = self.plan(amount=Decimal("0.10"))
        UpcomingExpensePayment.objects.bulk_create([
            UpcomingExpensePayment(
                plan=plan, payment_type=self.type, amount=Decimal("0.10"),
                scheduled_for=date(2027, 1 + i // 28, 1 + i % 28),
                due_date=date(2027, 1 + i // 28, 1 + i % 28),
            ) for i in range(52)
        ])
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["page"]), 50)
        self.assertEqual(response.context["page"].paginator.count, 53)
        self.assertEqual(response.context["totals"]["outstanding"], Decimal("5.30"))

    def test_stop_recurrence_preserves_outstanding_and_paid_installments(self):
        plan = self.plan(frequency="monthly", start_date=date(2026, 10, 10))
        materialize_monthly_payments(self.today)
        payment = plan.payments.first()
        set_payment_paid(payment.pk, True, self.user)
        response = self.client.post(self.url, {"action": "stop", "plan_id": plan.pk})
        self.assertEqual(response.status_code, 302)
        materialize_monthly_payments(date(2027, 1, 1))
        self.assertEqual(plan.payments.count(), 2)
        self.assertEqual(plan.payments.filter(is_paid=True).count(), 1)
        plan.refresh_from_db()
        self.assertFalse(plan.is_active)

    def test_edit_installment_does_not_duplicate_or_change_plan(self):
        plan = self.plan(frequency="monthly")
        payment = plan.payments.get()
        response = self.client.post(self.url, {
            "action": "edit", "payment_id": payment.pk,
            "edit-payment_type": self.type.pk, "edit-description": "Adjusted",
            "edit-amount": "123.45", "edit-due_date": "2026-11-20",
        })
        self.assertEqual(response.status_code, 302)
        materialize_monthly_payments(self.today)
        payment.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(payment.scheduled_for, date(2026, 11, 10))
        self.assertEqual(payment.due_date, date(2026, 11, 20))
        self.assertEqual(payment.amount, Decimal("123.45"))
        self.assertEqual(plan.amount, Decimal("100"))
        self.assertEqual(plan.payments.count(), 1)
        response = self.client.get(self.url, {"edit": payment.pk})
        self.assertContains(response, 'id="editExpense"')

    def test_paid_installment_cannot_be_edited(self):
        payment = self.plan().payments.get()
        set_payment_paid(payment.pk, True, self.user)
        self.client.post(self.url, {
            "action": "edit", "payment_id": payment.pk,
            "edit-payment_type": self.type.pk, "edit-amount": "500",
            "edit-due_date": "2026-12-01",
        })
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("100"))

    def test_add_types_and_reject_case_insensitive_duplicates(self):
        response = self.client.post(self.url, {"action": "create_type", "type-name": "Internet"})
        self.assertEqual(response.status_code, 302)
        response = self.client.post(self.url, {"action": "create_type", "type-name": "internet"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(UpcomingExpenseType.objects.filter(name__iexact="Internet").count(), 1)

    def test_invalid_amounts_and_dates_do_not_create_payments(self):
        for amount in ("0", "-10", "NaN", "1.001"):
            response = self.client.post(self.url, {
                "action": "create", "payment_type": self.type.pk,
                "amount": amount, "start_date": "2026-11-10", "frequency": "once",
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["create_form"].errors)
        self.assertFalse(UpcomingExpensePayment.objects.exists())
        response = self.client.get(self.url, {"due_from": "2026-12-01", "due_to": "2026-10-01"})
        self.assertTrue(response.context["filters"].errors)
        self.assertEqual(response.context["totals"]["outstanding"], Decimal("0"))

    def test_state_changes_require_post_and_csrf(self):
        payment = self.plan().payments.get()
        self.client.get(self.url, {"action": "paid", "payment_id": payment.pk, "paid": "yes"})
        payment.refresh_from_db()
        self.assertFalse(payment.is_paid)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(self.url, {"action": "paid", "payment_id": payment.pk, "paid": "yes"})
        self.assertEqual(response.status_code, 403)

    def test_malformed_ids_return_400(self):
        self.assertEqual(self.client.get(self.url, {"edit": "oops"}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"action": "paid", "payment_id": "oops"}).status_code, 400)

    def test_duplicate_paid_submissions_do_not_duplicate_installments(self):
        plan = self.plan(frequency="monthly")
        payment = plan.payments.get()
        for _ in range(2):
            self.client.post(self.url, {"action": "paid", "payment_id": payment.pk, "paid": "yes"})
        self.assertEqual(plan.payments.count(), 1)

    def test_admin_models_remain_superuser_only_even_with_permissions(self):
        staff = User.objects.create_user(username="model_staff", is_staff=True)
        staff.user_permissions.set(Permission.objects.filter(content_type__app_label="expenses"))
        request = RequestFactory().get("/")
        request.user = staff
        for model in (UpcomingExpenseType, UpcomingExpensePlan, UpcomingExpensePayment):
            admin = site._registry[model]
            self.assertFalse(admin.has_view_permission(request))
            self.assertFalse(admin.has_change_permission(request))
            self.assertFalse(admin.has_module_permission(request))

    def test_partial_payments_keep_original_and_deduct_only_paid_amount(self):
        payment = self.plan(amount=Decimal("1000")).payments.get()
        response = self.client.post(self.url, {
            "action": "partial", "payment_id": payment.pk, "payment_amount": "700",
        })
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("1000"))
        self.assertEqual(payment.amount_paid, Decimal("700"))
        self.assertEqual(payment.balance, Decimal("300"))
        self.assertFalse(payment.is_paid)
        page = self.client.get(self.url)
        self.assertEqual(page.context["totals"]["outstanding"], Decimal("300"))
        self.assertEqual(page.context["totals"]["paid_total"], Decimal("700"))
        self.assertContains(page, "Remaining 300.00")
        self.client.post(self.url, {"action": "partial", "payment_id": payment.pk, "payment_amount": "300"})
        payment.refresh_from_db()
        self.assertTrue(payment.is_paid)
        self.assertEqual(payment.receipts.count(), 2)
        self.assertEqual(self.client.get(self.url).context["page"].paginator.count, 0)
        self.client.post(self.url, {"action": "paid", "payment_id": payment.pk, "paid": "no"})
        payment.refresh_from_db()
        self.assertEqual(payment.balance, Decimal("1000"))
        self.assertEqual(payment.receipts.filter(is_reversed=True).count(), 2)

    def test_partial_overpayments_invalid_amounts_and_retries(self):
        from uuid import uuid4
        payment = self.plan().payments.get()
        for amount in ("101", "-5", "0", "NaN", "1.001"):
            self.client.post(self.url, {"action": "partial", "payment_id": payment.pk, "payment_amount": amount})
        payment.refresh_from_db()
        self.assertEqual(payment.amount_paid, 0)
        token = uuid4()
        for _ in range(2):
            self.client.post(self.url, {
                "action": "partial", "payment_id": payment.pk,
                "payment_amount": "30", "request_id": token,
            })
        payment.refresh_from_db()
        self.assertEqual(payment.amount_paid, Decimal("30"))
        self.assertEqual(payment.receipts.count(), 1)
        self.client.post(self.url, {"action": "paid", "payment_id": payment.pk, "paid": "yes"})
        payment.refresh_from_db()
        self.assertEqual(payment.amount_paid, Decimal("100"))
        self.assertEqual(payment.receipts.count(), 2)

    def schedule_data(self, plan, **overrides):
        data = {
            "action": "edit_plan", "plan_id": plan.pk,
            "plan-payment_type": self.type.pk, "plan-description": "Lebadvisor office",
            "plan-amount": "500", "plan-start_date": "2026-10-01",
            "plan-frequency": "monthly",
        }
        data.update(overrides)
        return data

    def test_sara_backdating_schedule_adds_october_without_duplicating_november(self):
        plan = self.plan(frequency="monthly", amount=Decimal("500"), start_date=date(2026, 11, 2))
        response = self.client.post(self.url, self.schedule_data(plan))
        self.assertEqual(response.status_code, 302)
        payments = plan.payments.filter(is_deleted=False)
        self.assertEqual(list(payments.values_list("scheduled_for", flat=True)), [
            date(2026, 10, 1), date(2026, 11, 1),
        ])
        materialize_monthly_payments(self.today)
        self.assertEqual(plan.payments.count(), 2)
        self.assertEqual(self.client.get(self.url).context["totals"]["outstanding"], Decimal("1000"))
        self.assertContains(self.client.get(self.url, {"edit_plan": plan.pk}), "Edit entire schedule")

    def test_schedule_changes_preserve_paid_and_partial_but_update_unpaid(self):
        from expenses.upcoming_services import record_partial_payment
        plan = self.plan(frequency="monthly", start_date=date(2026, 9, 10))
        materialize_monthly_payments(self.today)
        first, second, third = list(plan.payments.all())
        set_payment_paid(first.pk, True, self.user)
        record_partial_payment(second.pk, "40", self.user)
        self.client.post(self.url, self.schedule_data(plan, **{"plan-start_date": "2026-09-15"}))
        materialize_monthly_payments(self.today)
        self.assertEqual(plan.payments.count(), 3)
        first.refresh_from_db(); second.refresh_from_db(); third.refresh_from_db()
        self.assertEqual(first.amount, Decimal("100"))
        self.assertEqual(second.amount, Decimal("100"))
        self.assertEqual(second.balance, Decimal("60"))
        self.assertEqual(third.amount, Decimal("500"))
        self.assertEqual(third.due_date, date(2026, 11, 15))

    def test_delete_installment_does_not_reappear_or_delete_other_months(self):
        plan = self.plan(frequency="monthly", start_date=date(2026, 10, 10))
        materialize_monthly_payments(self.today)
        first = plan.payments.first()
        self.client.post(self.url, {"action": "delete", "payment_id": first.pk})
        materialize_monthly_payments(self.today)
        first.refresh_from_db()
        self.assertTrue(first.is_deleted)
        self.assertEqual(plan.payments.filter(is_deleted=False).count(), 1)
        self.assertEqual(self.client.get(self.url).context["totals"]["outstanding"], Decimal("100"))
        self.client.post(self.url, {"action": "delete_plan", "plan_id": plan.pk})
        self.assertEqual(self.client.get(self.url).context["page"].paginator.count, 0)
        materialize_monthly_payments(date(2027, 2, 1))
        self.assertEqual(plan.payments.count(), 2)

    def test_delete_protects_payment_history(self):
        from expenses.upcoming_services import record_partial_payment
        plan = self.plan()
        payment = plan.payments.get()
        record_partial_payment(payment.pk, "40", self.user)
        for data in (
            {"action": "delete", "payment_id": payment.pk},
            {"action": "delete_plan", "plan_id": plan.pk},
        ):
            self.client.post(self.url, data)
        payment.refresh_from_db(); plan.refresh_from_db()
        self.assertFalse(payment.is_deleted)
        self.assertFalse(plan.is_deleted)
        self.assertEqual(payment.amount_paid, Decimal("40"))

    def test_migration_preserves_existing_fully_paid_amounts(self):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        payment = self.plan().payments.get()
        payment.is_paid = True
        payment.save()
        migration = import_module("expenses.migrations.0004_expense_partial_payments_and_schedule_edits")
        from types import SimpleNamespace
        migration.preserve_paid_balances(apps, SimpleNamespace(connection=connection))
        payment.refresh_from_db()
        self.assertEqual(payment.amount_paid, payment.amount)

    def test_five_month_schedule_ends_and_keeps_all_records(self):
        plan = self.plan(frequency="monthly", start_date=date(2026, 11, 1), end_date=date(2027, 3, 1))
        materialize_monthly_payments(date(2028, 1, 1))
        self.assertEqual(plan.payments.count(), 5)
        self.assertEqual(list(plan.payments.values_list("scheduled_for", flat=True)), [
            date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1),
            date(2027, 2, 1), date(2027, 3, 1),
        ])
        for payment in plan.payments.all():
            set_payment_paid(payment.pk, True, self.user)
        materialize_monthly_payments(date(2028, 2, 1))
        self.assertEqual(plan.payments.count(), 5)
        self.assertEqual(plan.payments.filter(is_paid=True).count(), 5)

    def test_end_date_can_be_added_to_existing_schedule(self):
        plan = self.plan(frequency="monthly", start_date=date(2026, 7, 1))
        materialize_monthly_payments(self.today)
        first = plan.payments.first()
        set_payment_paid(first.pk, True, self.user)
        response = self.client.post(self.url, self.schedule_data(plan, **{
            "plan-start_date": "2026-07-01", "plan-end_date": "2026-10-01",
        }))
        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.end_date, date(2026, 10, 1))
        self.assertEqual(plan.payments.filter(is_deleted=False).count(), 4)
        self.assertTrue(plan.payments.get(pk=first.pk).is_paid)
        materialize_monthly_payments(date(2027, 1, 1))
        self.assertEqual(plan.payments.filter(is_deleted=False).count(), 4)

    def test_invalid_end_date_rejected(self):
        response = self.client.post(self.url, {
            "action": "create", "payment_type": self.type.pk, "amount": "500",
            "start_date": "2026-11-01", "end_date": "2026-10-01", "frequency": "monthly",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("end_date", response.context["create_form"].errors)
        self.assertFalse(UpcomingExpensePlan.objects.exists())

    def test_paid_check_label_and_state(self):
        payment = self.plan().payments.get()
        response = self.client.get(self.url)
        self.assertContains(response, 'aria-checked="false"')
        self.assertContains(response, '</span>Paid')
        set_payment_paid(payment.pk, True, self.user)
        response = self.client.get(self.url, {"status": "paid"})
        self.assertContains(response, 'aria-checked="true"')

    def test_stop_recurrence_is_visible_in_rows_and_expanded_section(self):
        plan = self.plan(frequency="monthly")
        response = self.client.get(self.url)
        self.assertContains(response, 'class="ep-panel ep-recurring" open')
        self.assertContains(response, "Stop recurrence", count=3)
        self.client.post(self.url, {"action": "stop", "plan_id": plan.pk})
        plan.refresh_from_db()
        self.assertFalse(plan.is_active)
        self.assertEqual(plan.payments.count(), 1)
