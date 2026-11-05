"""Шаг 05: мебельная вёрстка сохраняет доступ, фильтры и AJAX-контракты."""
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from apps.products.models import Category, Product


class FurnitureCatalogTests(TestCase):
    def setUp(self):
        from apps.products.tests.image_fixtures import image_test_storage
        image_test_storage(self, ['products/original-test.jpg'])
        cache.clear()
        self.category = Category.objects.create(title='Шкафы', slug='shkafy')
        self.item = Product.objects.create(title='Шкаф из дерева', slug='wood-wardrobe', category=self.category, price=120000)
        self.other = Product.objects.create(title='Кухня под размер', slug='kitchen-test', price=240000)
        self.hidden = Product.objects.create(title='Секретный черновик', slug='hidden-test', price=1, is_active=False)
        self.url = reverse('catalog:catalog')

    def test_furniture_shell_original_photo_and_currency(self):
        self.item.image = 'products/original-test.jpg'
        self.item.currency = 'USD'
        self.item.save(update_fields=['image', 'currency'])
        response = self.client.get(self.url)
        self.assertContains(response, 'Каталог мебели')
        self.assertContains(response, 'furniture-catalog.css')
        self.assertContains(response, '/media/products/original-test.jpg')
        self.assertContains(response, '.webp')
        self.assertContains(response, '120\u00a0000 $')
        self.assertNotContains(response, 'Каталог автомобилей')
        self.assertNotContains(response, 'themes/auto.css')
        self.assertNotContains(response, 'home/images/logo.png')
        self.assertNotContains(response, self.hidden.title)
        self.assertContains(response, 'href="/#portfolio"')
        self.assertContains(response, 'href="/wishlist/"')

    def test_category_search_price_and_sort_together(self):
        extra = Product.objects.create(title='Шкаф встроенный', slug='wardrobe-2', category=self.category, price=150000)
        response = self.client.get(self.url, {'category': self.category.pk, 'q': 'ШКАФ', 'price_min': 130000, 'sort': 'price_desc'})
        self.assertEqual(list(response.context['products']), [extra])
        self.assertEqual(response.context['furniture_category_title'], 'Шкафы')
        self.assertContains(response, 'Найдено изделий: 1')

    def test_empty_state_and_invalid_range_are_actionable(self):
        response = self.client.get(self.url, {'q': 'такого изделия нет'})
        self.assertContains(response, 'Подходящих изделий пока нет')
        self.assertContains(response, '/#callback')
        self.assertContains(response, 'Сбросить фильтры')
        response = self.client.get(self.url, {'price_min': '200', 'price_max': '100'}, HTTP_X_CATALOG_MODE='replace')
        self.assertContains(response, 'Проверьте диапазон')
        self.assertContains(response, 'catalog-filter-errors')

    def test_drafts_absent_from_both_ajax_modes(self):
        for headers in ({'HTTP_X_CATALOG_MODE': 'replace'}, {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}):
            response = self.client.get(self.url, **headers)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.hidden.title)

    def test_pagination_and_sort_preserve_category_search_and_legacy_parameters(self):
        response = self.client.get(self.url, {'category': self.category.pk, 'q': 'Шкаф', 'availability': 'in_stock', 'sort': 'price_desc'})
        self.assertContains(response, f'name="category" value="{self.category.pk}"')
        self.assertContains(response, 'name="availability" value="in_stock"')
        self.assertContains(response, 'name="q" value="Шкаф"')
        self.assertContains(response, 'Дополнительные условия')
        for i in range(5):
            Product.objects.create(title=f'Шкаф {i}', slug=f'wardrobe-{i}', category=self.category, price=100+i)
        response = self.client.get(self.url, {'category': self.category.pk, 'q': 'Шкаф', 'page': '2'})
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertContains(response, f'category={self.category.pk}&amp;q=')
        response = self.client.get(self.url, {'category': self.category.pk, 'page': 2}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIn('fc-card', response.json()['html'])
        self.assertIsInstance(response.json()['has_next'], bool)
        self.assertNotIn('catalog-filter-form', response.json()['html'])

    def test_direct_catalog_issues_csrf_for_existing_favorite_and_comparison_actions(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.url)
        self.assertIn('csrftoken', client.cookies)
        token = client.cookies['csrftoken'].value
        favorite = reverse('wishlist:toggle', args=[self.item.pk])
        self.assertEqual(client.post(favorite).status_code, 403)
        self.assertTrue(client.post(favorite, HTTP_X_CSRFTOKEN=token).json()['is_favorite'])
        comparison = reverse('catalog:toggle_comparison_ajax', args=[self.item.pk])
        self.assertTrue(client.post(comparison, HTTP_X_CSRFTOKEN=token).json()['is_added'])
        response = client.get(self.url)
        self.assertContains(response, 'В избранном')
        self.assertContains(response, 'compare-btn active')

    def test_query_is_escaped(self):
        payload = '<script>alert(1)</script>'
        response = self.client.get(self.url, {'q': payload})
        self.assertNotContains(response, payload)
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
