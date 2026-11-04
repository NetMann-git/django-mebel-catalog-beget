"""шаг 48: friendly 404 without changing routing or publication rules."""
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.products.models import Product


@override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
class FurnitureNotFoundTests(TestCase):
    def assert_furniture_404(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Страница не найдена', status_code=404)
        self.assertContains(response, 'noindex, follow', status_code=404)
        self.assertContains(response, 'href="' + reverse('catalog:catalog') + '"', status_code=404)
        self.assertContains(response, 'На главную →', status_code=404)
        self.assertNotContains(response, 'Page not found', status_code=404)
        self.assertNotContains(response, 'themes/auto.css', status_code=404)
        self.assertNotContains(response, 'Traceback', status_code=404)

    def test_unknown_path_and_missing_product_return_404(self):
        for url in ['/missing-furniture-page/', '/catalog/missing-furniture-product/']:
            self.assert_furniture_404(self.client.get(url))

    def test_inactive_product_remains_hidden(self):
        hidden = Product.objects.create(title='Секретное название изделия', slug='private-furniture',
                                        price=12345, is_active=False,
                                        description='Скрытое описание', image='products/private.jpg')
        response = self.client.get(hidden.get_absolute_url())
        self.assert_furniture_404(response)
        for text in [hidden.title, hidden.description, 'private.jpg', '12345']:
            self.assertNotContains(response, text, status_code=404)

    def test_request_path_is_not_reflected_into_html(self):
        response = self.client.get('/%3Cscript%3Ebad()%3C/script%3E/')
        self.assert_furniture_404(response)
        self.assertNotContains(response, '<script>bad()', status_code=404)

    def test_valid_public_pages_and_existing_debug_mode_are_preserved(self):
        for name in ['home', 'catalog:catalog', 'furniture_services', 'furniture_materials', 'furniture_reviews']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        with override_settings(DEBUG=True):
            response = self.client.get('/missing-furniture-page/')
            self.assertEqual(response.status_code, 404)
            self.assertContains(response, 'DEBUG', status_code=404)
            self.assertTemplateNotUsed(response, '404.html')
