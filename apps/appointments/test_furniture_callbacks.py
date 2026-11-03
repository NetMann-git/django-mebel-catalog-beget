"""Furniture callback management: private details and compatible status workflow."""
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.appointments.models import CallbackRequest
from apps.products.models import Product


class FurnitureCallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('callback-manager')
        self.user.profile.role = 'manager'
        self.user.profile.save()
        self.client.force_login(self.user)
        self.url = reverse('appointments:callback_request_list')
        self.product = Product.objects.create(title='Кухня по размерам', slug='kitchen-order', price=200000)
        self.draft = Product.objects.create(title='Проект шкафа', slug='draft-wardrobe', price=100000, is_active=False)
        self.comment = 'Подробности проекта.\n' + ('Размеры и материалы. ' * 15) + 'Конец обращения <script>alert("x")</script>'
        self.order = CallbackRequest.objects.create(name='Заказчик', phone='+79991234567',
            email='client@example.com', city='Тестовый город', comment=self.comment,
            product=self.product, source='product_order')
        self.question = CallbackRequest.objects.create(phone='+79991112233', product=self.product,
            source='product_detail', status='processed')
        self.home = CallbackRequest.objects.create(phone='+79990000000', source='homepage', status='cancelled')
        self.legacy = CallbackRequest.objects.create(phone='+79992223344', product=self.draft,
            source='old <source>')

    def status_url(self, callback=None):
        return reverse('appointments:callback_request_status_update', args=[(callback or self.order).pk])

    def test_furniture_details_full_comment_sources_and_safe_links(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LUSTRID.RU')
        self.assertContains(response, 'Заказ изготовления')
        self.assertContains(response, 'Вопрос об изделии')
        self.assertContains(response, 'Главная')
        self.assertContains(response, 'old &lt;source&gt;')
        self.assertContains(response, 'Конец обращения &lt;script&gt;')
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, 'tel:+79991234567')
        self.assertContains(response, 'mailto:client@example.com')
        self.assertContains(response, 'Тестовый город')
        self.assertContains(response, 'Без привязки к изделию')
        self.assertContains(response, 'noindex, nofollow')
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertIn('Конец обращения', soup.select_one('.fm-callbacks__comment').get_text())
        for form in soup.select('.fm-callbacks__status-form'):
            self.assertIsNone(form.find_parent('form'))
        draft = soup.find('article', attrs={'aria-labelledby': f'callback-title-{self.legacy.pk}'})
        self.assertIsNotNone(draft.find('a', href=reverse('catalog:product_edit', args=[self.draft.pk])))
        self.assertIsNone(draft.find('a', href=self.draft.get_absolute_url()))
        self.assertContains(response, self.product.get_absolute_url())

    def test_filter_counts_invalid_filter_and_empty_result(self):
        response = self.client.get(self.url, {'status': 'new'})
        self.assertEqual(response.context['total'], 4)
        self.assertEqual(response.context['new_count'], 2)
        self.assertEqual(set(response.context['callbacks'].values_list('pk', flat=True)),
                         {self.order.pk, self.legacy.pk})
        response = self.client.get(self.url, {'status': 'invalid'})
        self.assertEqual(response.context['status'], '')
        self.assertEqual(len(response.context['callbacks']), 4)
        CallbackRequest.objects.filter(status='processed').delete()
        response = self.client.get(self.url, {'status': 'processed'})
        self.assertContains(response, 'Нет обращений с этим статусом')
        self.assertContains(response, 'Сбросить фильтр')
        CallbackRequest.objects.all().delete()
        self.assertContains(self.client.get(self.url), 'Обращений пока нет')

    def test_status_save_retains_filter_and_does_not_rewrite_details(self):
        before = CallbackRequest.objects.values().get(pk=self.order.pk)
        response = self.client.post(self.status_url(), {'status': 'processed', 'current_filter': 'new'})
        self.assertRedirects(response, self.url + '?status=new', fetch_redirect_response=False)
        after = CallbackRequest.objects.values().get(pk=self.order.pk)
        self.assertEqual(after['status'], 'processed')
        for key in before:
            if key not in ('status', 'updated_at'):
                self.assertEqual(after[key], before[key])
        response = self.client.get(response.url)
        self.assertNotContains(response, f'id="callback-title-{self.order.pk}"')
        self.order.refresh_from_db()
        timestamp = self.order.updated_at
        self.client.post(self.status_url(), {'status': 'processed'})
        self.order.refresh_from_db()
        self.assertEqual(self.order.updated_at, timestamp)
        self.assertEqual(CallbackRequest.objects.count(), 4)

    def test_bad_status_get_and_csrf_do_not_modify_data(self):
        before = list(CallbackRequest.objects.order_by('pk').values())
        self.assertEqual(self.client.get(self.status_url()).status_code, 405)
        response = self.client.post(self.status_url(), {'status': 'invented', 'current_filter': 'https://example.com/'})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertEqual(list(CallbackRequest.objects.order_by('pk').values()), before)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.status_url(), {'status': 'processed'}).status_code, 403)
        self.assertEqual(list(CallbackRequest.objects.order_by('pk').values()), before)
        client.get(self.url + '?status=new')
        token = client.cookies['csrftoken'].value
        response = client.post(self.status_url(), {'status': 'processed', 'current_filter': 'new',
                                                  'csrfmiddlewaretoken': token})
        self.assertRedirects(response, self.url + '?status=new', fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processed')

    def test_access_customer_consultant_staff_anonymous_and_superuser(self):
        for role in ('customer', 'consultant'):
            user = get_user_model().objects.create_user(role, is_staff=True)
            user.profile.role = role
            user.profile.save()
            self.client.force_login(user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 302)
            self.assertNotContains(response, self.order.phone, status_code=302)
            self.assertEqual(self.client.post(self.status_url(), {'status': 'processed'}).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.status_url(), {'status': 'processed'}).status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'new')
        superuser = get_user_model().objects.create_superuser('super', password='test-only')
        self.client.force_login(superuser)
        self.assertContains(self.client.get(self.url), self.order.phone)
        user = get_user_model().objects.create_user('role-admin')
        user.profile.role = 'admin'
        user.profile.save()
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_get_does_not_mark_read_or_change_original_data(self):
        before = list(CallbackRequest.objects.order_by('pk').values())
        self.client.get(self.url)
        self.client.get(self.url, {'status': 'new'})
        self.assertEqual(list(CallbackRequest.objects.order_by('pk').values()), before)
        self.assertEqual(self.order.comment, self.comment)
