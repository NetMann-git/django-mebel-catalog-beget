from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
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

    @patch('apps.appointments.views._notify_saved_inquiry')
    def test_product_callback_reaches_inbox_with_the_selected_product(self, notify):
        product = Product.objects.create(title='Шкаф «Север»', slug='callback-north', price=10)
        page = product.get_absolute_url() + '?rating=5'
        self.assertContains(self.client.get(page), 'Изделие в заявке: <strong>Шкаф «Север»</strong>')
        response = self.client.post(reverse('appointments:callback_submit'), {
            'phone': '+79991234567', 'return_to': page, 'comment': 'Нужен в другом размере',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        inquiry = CallbackRequest.objects.get()
        self.assertEqual(inquiry.product, product)
        self.assertEqual(inquiry.source, 'product_callback')
        self.assertEqual(inquiry.comment, 'Нужен в другом размере')
        notify.assert_called_once_with(inquiry)

        self.client.force_login(get_user_model().objects.create_superuser('callback-inbox'))
        inbox = self.client.get(reverse('appointments:callback_request_list'))
        self.assertContains(inbox, 'Обратный звонок по изделию')
        self.assertContains(inbox, product.title)

    @patch('apps.appointments.views._notify_saved_inquiry')
    def test_callback_from_stale_product_page_is_still_saved(self, notify):
        product = Product.objects.create(title='Черновик', slug='callback-draft', price=10, is_active=False)
        response = self.client.post(reverse('appointments:callback_submit'), {
            'phone': '+79991234567', 'return_to': product.get_absolute_url(),
            'product': product.pk, 'source': 'product_order',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        inquiry = CallbackRequest.objects.get()
        self.assertIsNone(inquiry.product_id)
        self.assertEqual(inquiry.source, 'site_callback')
        notify.assert_called_once_with(inquiry)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        MANAGER_EMAILS=['manager@example.test'],
        SITE_URL='https://lustrid.ru',
    )
    def test_email_for_product_callback_contains_product_title_and_link(self):
        from django.core import mail
        from apps.appointments.notifications import send_email_notification

        product = Product.objects.create(title='Шкаф «Север»', slug='callback-mail', price=10)
        inquiry = CallbackRequest.objects.create(
            phone='+79991234567', source='product_callback', product=product,
        )
        self.assertTrue(send_email_notification(inquiry))
        self.assertIn('Обратный звонок по изделию', mail.outbox[0].subject)
        self.assertIn(product.title, mail.outbox[0].body)
        self.assertIn('https://lustrid.ru' + product.get_absolute_url(), mail.outbox[0].body)
