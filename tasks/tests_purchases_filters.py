from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from display.models import Lead
from tasks.models import LeadTask, Service
from tasks.purchases_filters import SORT_DUE_ASC, SORT_TRAVEL_ASC, apply_purchases_filters, order_purchases


class PurchasesFilterTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='purch1', password='pass')
        self.lead = Lead.objects.create(
            name='Buyer',
            phone='70111555',
            country_code='+961',
            assigned_to=self.user,
        )
        self.leadtask = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status='progress',
            travel_date=timezone.now() + timedelta(days=10),
        )
        self.early = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Hotel',
            supplier='YARDS',
            net='100',
            due_time=timezone.make_aware(datetime(2026, 3, 1, 12, 0)),
            is_checked=False,
        )
        self.late = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Visa',
            supplier='BABYLON',
            net='50',
            due_time=timezone.make_aware(datetime(2026, 6, 1, 12, 0)),
            is_checked=False,
        )

    def test_due_date_range_filter(self):
        qs = Service.objects.filter(due_time__isnull=False)
        filtered = apply_purchases_filters(
            qs,
            {'due_from': '2026-05-01', 'due_to': '2026-12-31', 'issued': 'unissued'},
            now=timezone.now(),
        )
        ids = list(filtered.values_list('pk', flat=True))
        self.assertIn(self.late.pk, ids)
        self.assertNotIn(self.early.pk, ids)

    def test_sort_by_travel_date(self):
        qs = Service.objects.filter(due_time__isnull=False)
        ordered = list(order_purchases(qs, SORT_TRAVEL_ASC))
        self.assertEqual(len(ordered), 2)

    def test_travel_date_range_filter(self):
        qs = Service.objects.all()
        filtered = apply_purchases_filters(
            qs,
            {
                'travel_from': '2026-06-01',
                'travel_to': '2026-12-31',
                'issued': 'unissued',
            },
            now=timezone.now(),
        )
        ids = list(filtered.values_list('pk', flat=True))
        self.assertIn(self.late.pk, ids)
        self.assertIn(self.early.pk, ids)

        self.leadtask.travel_date = timezone.make_aware(datetime(2026, 1, 15, 12, 0))
        self.leadtask.save(update_fields=['travel_date'])
        filtered = apply_purchases_filters(
            qs,
            {
                'travel_from': '2026-06-01',
                'travel_to': '2026-12-31',
                'issued': 'unissued',
            },
            now=timezone.now(),
        )
        ids = list(filtered.values_list('pk', flat=True))
        self.assertNotIn(self.early.pk, ids)
        self.assertNotIn(self.late.pk, ids)

    def test_excludes_past_and_missing_travel_dates_by_default(self):
        past_task = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status='progress',
            travel_date=timezone.now() - timedelta(days=5),
        )
        past_service = Service.objects.create(
            leadtask=past_task,
            service_name='Hotel',
            supplier='YARDS',
            net='80',
            due_time=timezone.now() + timedelta(days=2),
            is_checked=False,
        )
        no_travel_task = LeadTask.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            status='progress',
            travel_date=None,
        )
        no_travel_service = Service.objects.create(
            leadtask=no_travel_task,
            service_name='Visa',
            supplier='YARDS',
            net='40',
            due_time=timezone.now() + timedelta(days=2),
            is_checked=False,
        )
        qs = Service.objects.all()
        filtered = apply_purchases_filters(qs, {'issued': 'unissued'}, now=timezone.now())
        ids = list(filtered.values_list('pk', flat=True))
        self.assertIn(self.early.pk, ids)
        self.assertIn(self.late.pk, ids)
        self.assertNotIn(past_service.pk, ids)
        self.assertNotIn(no_travel_service.pk, ids)

    def test_missing_due_date_sorted_last(self):
        no_due = Service.objects.create(
            leadtask=self.leadtask,
            service_name='Transfer',
            supplier='YARDS',
            net='75',
            due_time=None,
            is_checked=False,
        )
        qs = Service.objects.all()
        filtered = apply_purchases_filters(qs, {'issued': 'unissued'}, now=timezone.now())
        ordered = list(order_purchases(filtered, SORT_DUE_ASC))
        self.assertEqual(ordered[-1].pk, no_due.pk)
        self.assertIn(no_due.pk, [s.pk for s in ordered])
