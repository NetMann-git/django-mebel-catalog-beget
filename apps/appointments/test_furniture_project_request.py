"""шаг 42: homepage description reaches the existing manager inbox safely."""
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client,TestCase
from django.urls import reverse
from apps.appointments.models import CallbackRequest


class FurnitureProjectRequestTests(TestCase):
    def setUp(self):
        self.url=reverse('appointments:callback_submit')
        self.inbox=reverse('appointments:callback_request_list')
        self.comment='Шкаф 180 см\nФасады <script>опасный текст</script>'
        self.payload={'name':'Анна','phone':'+79991234567','comment':self.comment}
        self.patches=[patch('apps.appointments.views.'+name) for name in ['send_email_notification','send_telegram_notification','send_max_notification']]
        self.notifications=[p.start() for p in self.patches]
        for p in self.patches:self.addCleanup(p.stop)

    def test_description_reaches_notifications_manager_and_status_workflow(self):
        client=Client(enforce_csrf_checks=True)
        home=client.get(reverse('home'))
        self.assertContains(home,'id="callback-comment"')
        self.assertContains(home,'Какую мебель вы хотите?')
        self.assertContains(home,'furniture-request.css')
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.url,self.payload,HTTP_X_REQUESTED_WITH='XMLHttpRequest').status_code,403)
        response=client.post(self.url,{**self.payload,'csrfmiddlewaretoken':token,'status':'processed','source':'product_order'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        record=CallbackRequest.objects.get()
        self.assertEqual(record.comment,self.comment)
        self.assertEqual(record.source,'homepage');self.assertEqual(record.status,'new');self.assertIsNone(record.product_id)
        for notify in self.notifications:
            notify.assert_called_once();self.assertEqual(notify.call_args.args[0].comment,self.comment)
        manager=get_user_model().objects.create_user('project-manager')
        manager.profile.role='manager';manager.profile.save(update_fields=['role'])
        client.force_login(manager)
        response=client.get(self.inbox)
        self.assertContains(response,'Шкаф 180 см')
        self.assertContains(response,'&lt;script&gt;опасный текст&lt;/script&gt;')
        self.assertNotContains(response,'<script>опасный текст</script>')
        token=client.cookies['csrftoken'].value
        status_url=reverse('appointments:callback_request_status_update',args=[record.pk])
        response=client.post(status_url,{'status':'processed','csrfmiddlewaretoken':token},follow=True)
        self.assertEqual(response.status_code,200)
        record.refresh_from_db();self.assertEqual(record.status,'processed');self.assertEqual(record.comment,self.comment)

    def test_description_is_optional_for_existing_call_only_requests(self):
        for comment in [None,'']:
            data={'name':'','phone':'+79991234567'}
            if comment is not None:data['comment']=comment
            response=self.client.post(self.url,data,HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertTrue(response.json()['success'])
        self.assertEqual(CallbackRequest.objects.count(),2)
        self.assertEqual(list(CallbackRequest.objects.values_list('comment',flat=True)),['',''])

    def test_invalid_phone_and_honeypot_do_not_store_description_or_notify(self):
        response=self.client.post(self.url,{**self.payload,'phone':'123'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code,400)
        self.assertIn('phone',response.json()['errors'])
        response=self.client.post(self.url,{**self.payload,'website':'spam'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        self.assertFalse(CallbackRequest.objects.exists())
        for notify in self.notifications:notify.assert_not_called()

    def test_plain_post_still_saves_and_returns_to_home(self):
        response=self.client.post(self.url,self.payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(response['Location'],reverse('home')+'#callback')
        self.assertEqual(CallbackRequest.objects.get().comment,self.comment)

    def test_customers_and_guests_cannot_read_description_in_inbox(self):
        CallbackRequest.objects.create(**self.payload)
        response=self.client.get(self.inbox,follow=True)
        self.assertNotContains(response,'Шкаф 180 см')
        customer=get_user_model().objects.create_user('project-customer');self.client.force_login(customer)
        response=self.client.get(self.inbox,follow=True)
        self.assertNotContains(response,'Шкаф 180 см')
