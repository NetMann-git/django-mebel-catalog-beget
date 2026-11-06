"""Workshop dashboard: real counts, compatible tools and private access."""
from datetime import time
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.appointments.models import Appointment, CallbackRequest
from apps.products.models import Product
from apps.reviews.models import Review
from apps.users.models import Profile


class FurnitureManagerTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user('workshop-manager')
        self.manager.profile.role = 'manager'
        self.manager.profile.save()
        self.client.force_login(self.manager)
        self.url = reverse('users:manager_dashboard')
        self.product = Product.objects.create(title='Шкаф', slug='wardrobe', price=100)
        Product.objects.create(title='Кухня', slug='kitchen', price=200)
        Product.objects.create(title='Скрытое изделие', slug='hidden-work', price=300, is_active=False)
        for status in ('new', 'processed', 'cancelled'):
            CallbackRequest.objects.create(name='Служебное имя', phone='+79990000000',
                comment='Конфиденциальный комментарий', status=status, product=self.product)
        Appointment.objects.create(name='Запись клиента', phone='+79990000001', date=timezone.now().date(),
                                   time=time(11, 0), product=self.product, user=self.manager)
        Review.objects.create(product=self.product, guest_name='Тест', rating=4, text='Отзыв')
        Review.objects.create(product=self.product, guest_name='Тест', rating=5, text='Отзыв')

    def test_real_counts_separate_callbacks_and_appointments(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['catalog_stats'], {'total': 3, 'published': 2, 'drafts': 1})
        self.assertEqual(response.context['callback_stats'], {'total': 3, 'new': 1, 'processed': 1, 'cancelled': 1})
        self.assertEqual(response.context['stats']['total'], 1)
        self.assertEqual(response.context['review_stats']['avg_rating'], 4.5)
        self.assertContains(response, reverse('appointments:callback_request_list') + '?status=new')
        self.assertNotContains(response, 'Конфиденциальный комментарий')
        self.assertNotContains(response, '+79990000000')

    def test_tools_preserved_but_separated_from_primary_navigation(self):
        response = self.client.get(self.url)
        soup = BeautifulSoup(response.content, 'html.parser')
        primary = soup.select_one('nav[aria-label="Управление мастерской"]')
        self.assertIsNotNone(primary)
        self.assertEqual(primary.select_one('a')['href'], reverse('catalog:product_list_manage'))
        self.assertNotIn('Encar', primary.get_text())
        for name in ('home:client_list_manage',):
            link = soup.find('a', href=reverse(name))
            self.assertIsNotNone(link)
            parent = link.find_parent('details')
            self.assertIsNotNone(parent)
            self.assertFalse(parent.has_attr('open'))
        self.assertNotContains(response, 'Импорт из Encar')
        self.assertNotContains(response, 'Модели автомобилей')
        self.assertContains(response, 'LUSTRID.RU')
        self.assertContains(response, 'Статистика записей')
        self.assertContains(response, 'noindex, nofollow')
        self.assertNotContains(response, 'статистика салона')

    def test_customer_consultant_staff_and_missing_profile_denied_before_queries(self):
        for role in ('customer', 'consultant'):
            user = get_user_model().objects.create_user(role, is_staff=True)
            user.profile.role = role
            user.profile.save()
            self.client.force_login(user)
            with patch('apps.users.views.Product.objects.aggregate', side_effect=AssertionError('must not query')):
                response = self.client.get(self.url)
            self.assertRedirects(response, reverse('users:dashboard'), fetch_redirect_response=False)
            self.assertNotContains(response, self.product.title, status_code=302)
        Profile.objects.filter(user=user).delete()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(parse_qs(urlparse(response.url).query)['next'], [self.url])

    def test_admin_and_superuser_with_default_customer_profile_allowed(self):
        user = get_user_model().objects.create_user('role-admin')
        user.profile.role = 'admin'
        user.profile.save()
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        superuser = get_user_model().objects.create_superuser('super', password='test-only')
        self.assertEqual(superuser.profile.role, 'customer')
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertContains(self.client.get(reverse('users:dashboard')), self.url)
        Profile.objects.filter(user=superuser).delete()
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_get_is_read_only(self):
        before = {model: list(model.objects.order_by('pk').values())
                  for model in (Product, CallbackRequest, Appointment, Review)}
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), rows)

    def test_empty_dashboard_counts_and_no_fictitious_rating(self):
        CallbackRequest.objects.all().delete()
        Appointment.objects.all().delete()
        Review.objects.all().delete()
        Product.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['catalog_stats']['total'], 0)
        self.assertEqual(response.context['callback_stats']['new'], 0)
        self.assertContains(response, 'Нет данных')
        self.assertNotContains(response, '0,0 / 5')
