from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.appointments.models import CallbackRequest
from apps.products.models import Product


class SharedCallbackTests(TestCase):
    def test_header_and_callback_render_once_on_furniture_pages(self):
        product = Product.objects.create(title='Шкаф', slug='shared-callback', price=10)
        urls = [reverse(name) for name in (
            'home', 'catalog:catalog', 'search:search', 'furniture_about',
            'furniture_services', 'furniture_materials', 'furniture_reviews',
            'furniture_contacts', 'public_offer', 'users:login',
        )]
        for url in [*urls, product.get_absolute_url()]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'id="callback"', count=1)
                self.assertContains(response, 'id="home-callback-form"', count=1)
                self.assertContains(response, 'id="callback-phone"', count=1)
                self.assertContains(response, 'id="callback-comment"', count=1)
                self.assertContains(response, 'home-callback.js', count=1)
                self.assertContains(response, 'href="#callback">Заказать звонок', count=2)
                main_link = 'href="/" aria-current="page">Главная' if url == '/' else 'href="/">Главная'
                self.assertContains(response, 'aria-label="Основная навигация"><a ' + main_link, count=1)

    @patch('apps.appointments.views._notify_saved_inquiry')
    def test_plain_submit_returns_to_the_same_page_with_feedback(self, notify):
        client = Client(enforce_csrf_checks=True)
        page = reverse('catalog:catalog') + '?q=F-204'
        response = client.get(page)
        self.assertContains(response, f'name="return_to" value="{page}"')
        token = client.cookies['csrftoken'].value
        url = reverse('appointments:callback_submit')
        data = {'csrfmiddlewaretoken': token, 'return_to': page, 'phone': '123'}

        invalid = client.post(url, data, follow=True)
        self.assertEqual(invalid.redirect_chain, [(page + '#callback', 302)])
        self.assertContains(invalid, 'home-callback__feedback--error')
        self.assertFalse(CallbackRequest.objects.exists())
        notify.assert_not_called()

        valid = client.post(url, {**data, 'phone': '+79991234567'}, follow=True)
        self.assertEqual(valid.redirect_chain, [(page + '#callback', 302)])
        self.assertContains(valid, 'home-callback__feedback--success')
        self.assertEqual(CallbackRequest.objects.get().source, 'site_callback')

    def test_plain_submit_rejects_external_destinations(self):
        for target in ('//example.test', 'https://example.test', '/\\example.test'):
            with self.subTest(target=target):
                response = self.client.post(reverse('appointments:callback_submit'), {
                    'return_to': target, 'website': 'blocked by honeypot',
                })
                self.assertRedirects(response, '/#callback', fetch_redirect_response=False)

    def test_staff_product_preview_has_no_customer_form(self):
        self.client.force_login(get_user_model().objects.create_superuser('callback-preview'))
        product = Product.objects.create(title='Шкаф', slug='preview-callback', price=10, is_active=False)
        response = self.client.get(reverse('catalog:product_preview', args=[product.pk]))
        self.assertNotContains(response, 'id="home-callback-form"')
