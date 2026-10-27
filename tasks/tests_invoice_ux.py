from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from display.models import Lead
from tasks.models import Attachment, LeadTask, Payment, Service
from tasks.datetime_safety import services_for_client_pdf, services_for_leadtask


class InvoiceInlineActionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("invoice_user", password="pass")
        self.client.login(username="invoice_user", password="pass")
        lead = Lead.objects.create(
            name="Inline actions",
            phone="70111111",
            assigned_to=self.user,
        )
        self.order = LeadTask.objects.create(
            lead=lead, assigned_to=self.user, status="progress"
        )
        self.service = Service.objects.create(
            leadtask=self.order,
            service_name="Hotel",
            supplier="BABYLON",
            net="100",
        )

    def invoice_data(self, services):
        data = {'status': 'progress', 'assigned_to': self.user.pk}
        for service, position in services:
            for field in (
                'service_name', 'supplier', 'details', 'net', 'issue_price',
                'selling', 'voucher_id',
            ):
                data[f'service_{service.pk}_{field}'] = getattr(service, field)
            data[f'service_{service.pk}_due_time'] = ''
            data[f'service_{service.pk}_is_checked'] = 'on' if service.is_checked else ''
            data[f'service_{service.pk}_send_to_client'] = 'on' if service.send_to_client else ''
            if position is not None:
                data[f'service_{service.pk}_sort_order'] = position
        return data

    def test_invoice_save_persists_service_order_without_changing_flags(self):
        self.service.send_to_client = True
        self.service.is_checked = True
        self.service.save()
        second = Service.objects.create(
            leadtask=self.order, service_name='Visa', supplier='BABYLON',
        )
        response = self.client.post(
            f'/tasks/leads/edit/{self.order.pk}/',
            self.invoice_data([(self.service, 2), (second, 1)]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(services_for_leadtask(self.order).values_list('pk', flat=True)),
            [second.pk, self.service.pk],
        )
        self.assertEqual(
            list(services_for_client_pdf(self.order).values_list('pk', flat=True)),
            [second.pk, self.service.pk],
        )
        self.service.refresh_from_db()
        self.assertTrue(self.service.send_to_client)
        self.assertTrue(self.service.is_checked)

    def test_new_service_can_be_reordered_before_existing_service(self):
        data = self.invoice_data([(self.service, 2)])
        data.update({
            'service_name[]': ['Visa', 'Transfer'],
            'supplier[]': ['BABYLON', 'BABYLON'],
            'sort_order[]': ['1', '3'],
            'send_to_client[]': ['', ''],
        })
        response = self.client.post(f'/tasks/leads/edit/{self.order.pk}/', data)
        self.assertEqual(response.status_code, 302)
        services = list(services_for_leadtask(self.order))
        self.assertEqual([s.service_name for s in services], ['Visa', 'Hotel', 'Transfer'])
        self.assertFalse(services[0].send_to_client)
        appended = Service.objects.create(leadtask=self.order, service_name='Tours')
        self.assertEqual(appended.sort_order, 4)

    def test_old_posts_without_positions_keep_existing_order(self):
        original = self.service.sort_order
        response = self.client.post(
            f'/tasks/leads/edit/{self.order.pk}/',
            self.invoice_data([(self.service, None)]),
        )
        self.assertEqual(response.status_code, 302)
        self.service.refresh_from_db()
        self.assertEqual(self.service.sort_order, original)

    def test_reordering_cannot_modify_another_order(self):
        other = LeadTask.objects.create(
            lead=self.order.lead, assigned_to=self.user, status='progress',
        )
        other_service = Service.objects.create(leadtask=other, service_name='Visa')
        original = other_service.sort_order
        data = self.invoice_data([(self.service, 1), (other_service, 99)])
        response = self.client.post(f'/tasks/leads/edit/{self.order.pk}/', data)
        self.assertEqual(response.status_code, 302)
        other_service.refresh_from_db()
        self.assertEqual(other_service.sort_order, original)

    def test_invoice_table_has_reorder_controls_and_sent_column(self):
        response = self.client.get(f'/tasks/leads/edit/{self.order.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="service-move-up"')
        self.assertContains(response, 'class="service-move-down"')
        self.assertContains(response, '<th>Sent to client</th>', count=1)
        self.assertContains(response, 'class="service-send-to-client-cb"')
        self.assertNotContains(response, '<label>Send to Client</label>')
        self.assertContains(response, f'name="service_{self.service.pk}_send_to_client"')

    def test_sent_to_client_toggle_can_be_set_and_unset(self):
        for value, expected in [('on', True), ('off', False)]:
            response = self.client.post(
                f'/tasks/service/update_send_to_client/{self.service.pk}/',
                {'send_to_client': value},
            )
            self.assertEqual(response.status_code, 200)
            self.service.refresh_from_db()
            self.assertEqual(self.service.send_to_client, expected)

    def test_new_services_keep_independent_sent_to_client_flags(self):
        data = self.invoice_data([(self.service, 1)])
        data.update({
            'service_name[]': ['Visa', 'Transfer', 'Hotel'],
            'details[]': ['first', 'second', 'third'],
            'supplier[]': ['BABYLON', 'BABYLON', 'BABYLON'],
            'send_to_client[]': ['', 'on', ''],
        })
        response = self.client.post(f'/tasks/leads/edit/{self.order.pk}/', data)
        self.assertEqual(response.status_code, 302)
        created = self.order.service_set.exclude(pk=self.service.pk).order_by('pk')
        self.assertEqual(list(created.values_list('send_to_client', flat=True)), [False, True, False])

    def test_attachments_can_be_reordered_without_changing_files(self):
        first = Attachment.objects.create(
            parentleadtask=self.order, attachment_name='Visa.pdf', file='visa.pdf',
        )
        second = Attachment.objects.create(
            parentleadtask=self.order, attachment_name='Hotel.pdf', file='hotel.pdf',
        )
        data = self.invoice_data([(self.service, 1)])
        data['attachment_order[]'] = [str(second.pk), str(first.pk)]
        response = self.client.post(f'/tasks/leads/edit/{self.order.pk}/', data)
        self.assertEqual(response.status_code, 302)
        ordered = Attachment.objects.filter(parentleadtask=self.order)
        self.assertEqual(list(ordered.values_list('pk', flat=True)), [second.pk, first.pk])
        self.assertEqual(
            list(ordered.values_list('attachment_name', 'file')),
            [('Hotel.pdf', 'hotel.pdf'), ('Visa.pdf', 'visa.pdf')],
        )
        page = self.client.get(f'/tasks/leads/edit/{self.order.pk}/')
        self.assertEqual([a.pk for a in page.context['attachments']], [second.pk, first.pk])
        self.assertContains(page, 'class="attachment-move-up"')
        self.assertContains(page, 'name="attachment_order[]"')
        appended = Attachment.objects.create(
            parentleadtask=self.order, attachment_name='New.pdf', file='new.pdf',
        )
        self.assertEqual(appended.sort_order, 3)

    def test_attachment_reordering_ignores_foreign_and_duplicate_ids(self):
        other_order = LeadTask.objects.create(
            lead=self.order.lead, assigned_to=self.user, status='progress',
        )
        foreign = Attachment.objects.create(
            parentleadtask=other_order, attachment_name='Other.pdf', file='other.pdf',
        )
        first = Attachment.objects.create(
            parentleadtask=self.order, attachment_name='First.pdf', file='first.pdf',
        )
        second = Attachment.objects.create(
            parentleadtask=self.order, attachment_name='Second.pdf', file='second.pdf',
        )
        data = self.invoice_data([])
        data['attachment_order[]'] = [str(second.pk), str(second.pk), str(foreign.pk), 'invalid']
        response = self.client.post(f'/tasks/leads/edit/{self.order.pk}/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(Attachment.objects.filter(parentleadtask=self.order).values_list('pk', flat=True)),
            [second.pk, first.pk],
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.sort_order, 1)

    def test_posts_without_attachment_order_preserve_it(self):
        attachment = Attachment.objects.create(
            parentleadtask=self.order, attachment_name='File.pdf',
            file='file.pdf', sort_order=7,
        )
        response = self.client.post(
            f'/tasks/leads/edit/{self.order.pk}/', self.invoice_data([]),
        )
        self.assertEqual(response.status_code, 302)
        attachment.refresh_from_db()
        self.assertEqual(attachment.sort_order, 7)

    def test_service_modal_can_save_as_json_without_page_redirect(self):
        response = self.client.post(
            f"/tasks/services/update/{self.service.pk}/",
            {
                "service_name": "Hotel",
                "supplier": "BABYLON",
                "details": "Updated inline",
                "net": "120",
                "issue_price": "",
                "selling": "180",
                "due_time": "",
                "voucher_id": "",
                "is_checked": "",
                "send_to_client": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.service.refresh_from_db()
        self.assertEqual(self.service.details, "Updated inline")

    def test_payment_can_be_added_as_json_without_page_redirect(self):
        response = self.client.post(
            f"/tasks/payment/{self.order.pk}/",
            {"amount": "250", "date": "2026-07-21"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(
            Payment.objects.filter(leadtask=self.order, amount=250).exists()
        )

    def test_payment_amount_and_date_can_be_edited(self):
        payment = Payment.objects.create(
            leadtask=self.order,
            amount=100,
            date=timezone.make_aware(datetime(2026, 7, 1, 12, 0)),
        )
        response = self.client.post(
            f"/tasks/payments/update/{payment.pk}/",
            {"amount": "275", "date": "2026-08-15"},
        )
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.amount, 275)
        self.assertEqual(payment.date.date().isoformat(), "2026-08-15")
