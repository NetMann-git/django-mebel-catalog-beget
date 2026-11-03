"""шаг 35: own appointment history and safe furniture rendering."""
from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product
from apps.appointments.models import Appointment


class FurniturePersonalAppointmentsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('appointment-owner')
        self.other = get_user_model().objects.create_user('appointment-other')
        self.product = Product.objects.create(title='<script>Шкаф</script>', slug='appointment-case', price=100)
        self.url = reverse('users:appointments')

    def create(self, user, hour, **kwargs):
        return Appointment.objects.create(user=user, name='Клиент', phone='000', date=date(2026,11,10), time=time(hour), **kwargs)

    def test_only_own_records_in_existing_date_order_and_no_private_details(self):
        first = self.create(self.user, 10, product=self.product, comment='Скрытый комментарий', email='private@example.test')
        second = self.create(self.user, 12, status='cancelled')
        self.create(self.other, 13, product=self.product, comment='Чужие сведения')
        self.create(None, 14, product=self.product)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['appointments']), [second, first])
        for text in ['furniture-appointments.css', 'noindex, nofollow', '10.11.2026', '10:00', '12:00',
                     '&lt;script&gt;Шкаф&lt;/script&gt;', self.product.get_absolute_url(),
                     'Ожидает подтверждения', 'Отменена', reverse('users:dashboard')]:
            self.assertContains(response, text)
        for text in ['<script>Шкаф', 'Скрытый комментарий', 'private@example.test', 'Чужие сведения', '13:00', '14:00', 'примерку', 'themes/auto.css']:
            self.assertNotContains(response, text)
        self.assertEqual(Appointment.objects.count(), 4)
        first.refresh_from_db()
        self.assertEqual(first.comment, 'Скрытый комментарий')

    def test_all_existing_status_labels_are_retained_without_product(self):
        records = [self.create(self.user, 10+i, status=status) for i,(status,_) in enumerate(Appointment.STATUS_CHOICES)]
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        for _, label in Appointment.STATUS_CHOICES:
            self.assertContains(response, label)
        self.assertEqual(len(response.context['appointments']), len(records))
        self.assertContains(response, '<dd>—</dd>', count=len(records))

    def test_empty_state_ignores_foreign_appointments(self):
        self.create(self.other, 11, product=self.product)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, 'У вас пока нет записей.')
        self.assertContains(response, reverse('catalog:catalog'))
        self.assertNotContains(response, self.product.get_absolute_url())

    def test_guest_must_login(self):
        response = self.client.get(self.url, follow=True)
        self.assertEqual(response.redirect_chain, [(reverse('users:login')+'?next='+self.url,302)])
        self.assertEqual(response.status_code, 200)
