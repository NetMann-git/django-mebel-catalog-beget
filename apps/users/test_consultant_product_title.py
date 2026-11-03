"""шаг 36: consultant rows must use the existing Product.title field."""
from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product
from apps.appointments.models import Appointment


class ConsultantProductTitleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('consultant-title')
        self.product = Product.objects.create(title='<b>Шкаф из дуба</b>', slug='consultant-oak', price=100)
        self.record = Appointment.objects.create(product=self.product, name='Закрытое имя клиента', phone='123456789', date=date(2026,11,10),time=time(10),status='cancelled')
        self.url = reverse('users:consultant_dashboard')
        self.client.force_login(self.user)

    def test_authorized_roles_see_escaped_title_and_existing_status_form(self):
        for role in ['consultant', 'manager', 'admin']:
            with self.subTest(role=role):
                self.user.profile.role = role
                self.user.profile.save(update_fields=['role'])
                response = self.client.get(self.url)
                self.assertContains(response, '&lt;b&gt;Шкаф из дуба&lt;/b&gt;')
                self.assertNotContains(response, '<b>Шкаф из дуба</b>')
                self.assertContains(response, reverse('users:appointment_update_status', args=[self.record.pk]))
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertContains(response, 'value="cancelled" selected')
                self.assertEqual(response.context['stats']['total'], 1)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, 'cancelled')

    def test_long_title_stays_truncated_and_missing_product_still_renders(self):
        self.user.profile.role = 'consultant'
        self.user.profile.save(update_fields=['role'])
        self.product.title = 'Шкаф ' + 'длинное название ' * 8
        self.product.save(update_fields=['title'])
        response = self.client.get(self.url)
        from django.template.defaultfilters import truncatechars
        self.assertContains(response, truncatechars(self.product.title,30))
        self.assertNotContains(response, self.product.title)
        self.record.product = None
        self.record.save(update_fields=['product'])
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_customer_and_guest_cannot_see_customer_data(self):
        response = self.client.get(self.url, follow=True)
        self.assertEqual(response.redirect_chain, [(reverse('users:dashboard'),302)])
        self.assertNotContains(response, self.record.name)
        self.assertNotContains(response, self.record.phone)
        self.client.logout()
        response = self.client.get(self.url, follow=True)
        self.assertEqual(response.redirect_chain, [(reverse('users:login')+'?next='+self.url,302)])
        self.assertNotContains(response, self.record.name)
        self.assertNotContains(response, self.record.phone)
