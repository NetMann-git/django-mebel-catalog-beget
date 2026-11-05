"""Шаг 70: сбой уведомления не отменяет подтверждение сохранённого обращения."""
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.products.models import Product
from .models import CallbackRequest

class NotificationIsolationTests(TestCase):
    def setUp(self):
        self.product=Product.objects.create(title='Шкаф на заказ',slug='notification-test',price=100)
        self.data={'name':'Анна','phone':'+79991234567','city':'Сочи',
                   'email':'test@example.test','comment':'Шкаф 180 см'}
        self.channels=[]
        for name in ['send_email_notification','send_telegram_notification','send_max_notification']:
            p=patch('apps.appointments.views.'+name);self.channels.append(p.start());self.addCleanup(p.stop)

    def test_each_failure_keeps_success_for_home_and_product_plain_and_ajax(self):
        home=reverse('appointments:callback_submit')
        product=reverse('appointments:car_inquiry',args=[self.product.pk])
        cases=[(home,{},'homepage'),(home,{'HTTP_X_REQUESTED_WITH':'XMLHttpRequest'},'homepage'),
               (product,{},'product_detail'),(product+'?type=order',{},'product_order'),
               (product+'?type=order',{'HTTP_X_REQUESTED_WITH':'XMLHttpRequest'},'product_order')]
        for index,(url,headers,source) in enumerate(cases):
            with self.subTest(url=url,ajax=bool(headers)):
                for notify in self.channels:
                    notify.reset_mock();notify.side_effect=None
                self.channels[index%3].side_effect=RuntimeError('private contact details must not be logged')
                before=CallbackRequest.objects.count()
                with self.assertLogs('apps.appointments.views',level='ERROR') as logs:
                    response=self.client.post(url,self.data,**headers)
                self.assertEqual(CallbackRequest.objects.count(),before+1)
                record=CallbackRequest.objects.latest('pk')
                self.assertEqual(record.source,source)
                self.assertEqual(record.comment,self.data['comment'])
                self.assertEqual(record.product_id,None if source=='homepage' else self.product.pk)
                if headers:self.assertEqual(response.status_code,200);self.assertTrue(response.json()['success'])
                else:self.assertEqual(response.status_code,302)
                for notify in self.channels:notify.assert_called_once_with(record)
                self.assertNotIn('private contact',str(logs.output))
                self.assertNotIn(self.data['phone'],str(logs.output))

    def test_all_channels_can_fail_while_request_remains_visible_to_manager(self):
        for notify in self.channels:notify.side_effect=ValueError('channel unavailable')
        with self.assertLogs('apps.appointments.views',level='ERROR'):
            response=self.client.post(reverse('appointments:callback_submit'),self.data,HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        manager=get_user_model().objects.create_user('notify-manager')
        manager.profile.role='manager';manager.profile.save(update_fields=['role']);self.client.force_login(manager)
        response=self.client.get(reverse('appointments:callback_request_list'))
        self.assertContains(response,'Шкаф 180 см');self.assertContains(response,self.data['phone'])
        self.assertEqual(CallbackRequest.objects.count(),1)

    @override_settings(TELEGRAM_BOT_TOKEN=None)
    def test_real_adapter_configuration_error_does_not_stop_other_channels(self):
        from .notifications import send_telegram_notification
        self.channels[1].side_effect=send_telegram_notification
        with self.assertLogs('apps.appointments.views',level='ERROR'):
            response=self.client.post(reverse('appointments:callback_submit'),self.data,HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success']);self.assertEqual(CallbackRequest.objects.count(),1)
        self.channels[2].assert_called_once()

    def test_false_return_from_one_channel_does_not_stop_the_rest(self):
        self.channels[0].return_value=False
        response=self.client.post(reverse('appointments:callback_submit'),self.data,HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        for notify in self.channels:notify.assert_called_once()
