from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CallbackRequest


class CallbackFollowUpTests(TestCase):
    def setUp(self):
        manager = get_user_model().objects.create_user('follow-up-manager')
        manager.profile.role = 'manager'
        manager.profile.save(update_fields=['role'])
        self.client.force_login(manager)
        self.inbox = reverse('appointments:callback_request_list')
        self.today = timezone.localdate()
        self.request = CallbackRequest.objects.create(
            name='Анна', phone='+79991234567', comment='Шкаф в прихожую',
        )
        self.update = reverse('appointments:callback_request_status_update', args=[self.request.pk])

    def test_schedule_contact_then_close_without_losing_notes(self):
        self.assertRedirects(self.client.post(self.update, {
            'status': 'new', 'follow_up_on': self.today.isoformat(),
            'manager_note': 'Согласовали размеры <проверено>',
        }), self.inbox)
        self.request.refresh_from_db()
        self.assertEqual(self.request.follow_up_on, self.today)
        self.assertEqual(self.request.comment, 'Шкаф в прихожую')
        self.assertEqual(self.request.manager_note, 'Согласовали размеры <проверено>')

        due_url = self.inbox + '?due=1'
        response = self.client.get(due_url)
        self.assertContains(response, 'Связаться сегодня')
        self.assertContains(response, 'Согласовали размеры &lt;проверено&gt;')
        dashboard = self.client.get(reverse('users:manager_dashboard'))
        self.assertContains(dashboard, due_url)
        self.assertEqual(dashboard.context['callback_stats']['due'], 1)

        self.assertRedirects(self.client.post(self.update, {
            'status': 'processed', 'current_due': '1',
        }), due_url)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'processed')
        self.assertEqual(self.request.follow_up_on, self.today)
        self.assertEqual(self.request.manager_note, 'Согласовали размеры <проверено>')
        self.assertFalse(list(self.client.get(due_url).context['callbacks']))

    def test_due_queue_excludes_future_and_closed_and_orders_oldest_due_first(self):
        self.request.follow_up_on = self.today
        self.request.save(update_fields=['follow_up_on'])
        earlier = CallbackRequest.objects.create(
            phone='+79991234568', follow_up_on=self.today - timedelta(days=2),
        )
        CallbackRequest.objects.create(phone='+79991234569', follow_up_on=self.today + timedelta(days=1))
        CallbackRequest.objects.create(phone='+79991234560', follow_up_on=self.today, status='cancelled')
        CallbackRequest.objects.create(phone='+79991234561')
        response = self.client.get(self.inbox, {'due': '1'})
        self.assertEqual(list(response.context['callbacks']), [earlier, self.request])
        self.assertContains(response, 'Просрочено')

    def test_validation_clearing_and_public_form_boundaries(self):
        self.request.follow_up_on = self.today
        self.request.save(update_fields=['follow_up_on'])
        response = self.client.post(self.update, {
            'status': 'processed', 'follow_up_on': '9999-55-01', 'manager_note': 'Не должно сохраниться',
        }, follow=True)
        self.assertContains(response, 'Дата следующего контакта:')
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'new')
        self.assertEqual(self.request.follow_up_on, self.today)
        self.assertEqual(self.request.manager_note, '')

        self.client.post(self.update, {'status': 'new', 'follow_up_on': ''})
        self.request.refresh_from_db()
        self.assertIsNone(self.request.follow_up_on)

        self.client.force_login(get_user_model().objects.create_user('follow-up-customer'))
        self.assertEqual(self.client.get(self.inbox).status_code, 302)
        self.assertEqual(self.client.post(self.update, {'status': 'processed'}).status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'new')
        with patch('apps.appointments.views._notify_saved_inquiry'):
            self.client.post(reverse('appointments:callback_submit'), {
                'phone': '+79991234567', 'follow_up_on': self.today.isoformat(),
                'manager_note': 'Подставленная заметка', 'status': 'processed',
            })
        new_request = CallbackRequest.objects.latest('pk')
        self.assertNotEqual(new_request.pk, self.request.pk)
        self.assertEqual(new_request.status, 'new')
        self.assertEqual(new_request.manager_note, '')
        self.assertIsNone(new_request.follow_up_on)

    def test_future_and_unplanned_queues_and_return_after_scheduling(self):
        later = CallbackRequest.objects.create(
            phone='+79991234568', follow_up_on=self.today + timedelta(days=3),
        )
        sooner = CallbackRequest.objects.create(
            phone='+79991234569', follow_up_on=self.today + timedelta(days=1),
        )
        CallbackRequest.objects.create(phone='+79991234560', status='processed')
        future = self.inbox + '?queue=upcoming'
        unplanned = self.inbox + '?queue=unplanned'

        response = self.client.get(future)
        self.assertEqual(list(response.context['callbacks']), [sooner, later])
        self.assertEqual(response.context['pagination_query'], 'queue=upcoming')
        self.assertEqual(response.context['counts']['upcoming'], 2)
        self.assertEqual(list(self.client.get(unplanned).context['callbacks']), [self.request])

        self.assertRedirects(self.client.post(self.update, {
            'status': 'new',
            'follow_up_on': self.today.isoformat(),
            'current_queue': 'unplanned',
        }), unplanned)
        self.assertFalse(list(self.client.get(unplanned).context['callbacks']))
        self.assertEqual(list(self.client.get(self.inbox + '?due=1').context['callbacks']), [self.request])
