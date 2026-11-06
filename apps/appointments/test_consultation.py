"""Consultation pages, notifications and existing booking workflow."""
from datetime import date, time
from django.core import mail
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.products.models import Product
from .models import Appointment, WorkingHours


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   ADMIN_EMAIL='admin@example.test', DEFAULT_FROM_EMAIL='workshop@example.test',
                   SITE_URL='https://lustrid.ru')
class ConsultationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='Шкаф по размерам', slug='consultation-wardrobe', price=100)
        self.day = date(2027, 2, 1)
        WorkingHours.objects.create(day_of_week=self.day.weekday(), start_time=time(10), end_time=time(12))

    def data(self, **extra):
        return {'name': 'Анна', 'phone': '+79990000000', 'email': 'client@example.test',
                'date': self.day.isoformat(), 'time': '10:00', 'comment': 'Ширина 180 см', **extra}

    def assert_furniture(self, text):
        for old in ['примерк', 'Платье:', 'Wedding Salon', 'Тверская', '15 минут']:
            self.assertNotIn(old, text)

    def test_public_form_and_ajax_use_furniture_text(self):
        for ajax in [False, True]:
            response = self.client.get(reverse('appointments:form_for_product', args=[self.product.pk]),
                **({'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}))
            self.assertContains(response, 'Записаться на консультацию')
            self.assertContains(response, 'Изделие:')
            self.assertContains(response, self.product.title)
            self.assertContains(response, 'Дата консультации')
            self.assert_furniture(response.content.decode())
            if not ajax:
                self.assertContains(response, 'data-consultation-form')
                self.assertContains(response, 'appointments/js/consultation.js')
                self.assertContains(response, reverse('furniture_contacts'))

    def test_submit_without_product_redirects_to_catalog_and_sends_correct_emails(self):
        response = self.client.post(reverse('appointments:submit'), self.data())
        self.assertRedirects(response, reverse('catalog:catalog'), fetch_redirect_response=False)
        self.assertEqual(Appointment.objects.get().status, 'pending')
        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertIn('консультацию', message.subject)
            self.assert_furniture(message.subject + message.alternatives[0][0])
        self.assertIn('требуют подтверждения', mail.outbox[1].alternatives[0][0])
        self.assertNotIn('+7 (999) 123-45-67', mail.outbox[1].alternatives[0][0])

    def test_product_booking_retains_link_and_blocks_slot(self):
        response = self.client.post(reverse('appointments:submit'), self.data(product=self.product.pk),
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(Appointment.objects.get().product_id, self.product.pk)
        slots = self.client.get(reverse('appointments:slots', args=[self.day.isoformat()])).json()['slots']
        self.assertFalse(next(slot for slot in slots if slot['time'] == '10:00')['available'])
        duplicate = self.client.post(reverse('appointments:submit'), self.data(product=self.product.pk),
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_admin_consultation_labels_and_form_save_existing_record(self):
        item = Appointment.objects.create(product=self.product, name='Анна', phone='+79990000000',
                                          date=self.day, time=time(10))
        self.client.force_login(get_user_model().objects.create_superuser('consult-admin', 'admin@example.test', 'test-pass'))
        response = self.client.get(reverse('admin:appointments_appointment_change', args=[item.pk]))
        self.assertContains(response, 'Дата консультации')
        self.assertContains(response, 'Время консультации')
        self.assert_furniture(response.content.decode())
        self.assertEqual(Appointment._meta.verbose_name_plural, 'Записи на консультацию')
