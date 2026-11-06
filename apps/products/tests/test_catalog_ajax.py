"""Catalog filtering and the two independent AJAX response contracts."""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.products.models import Brand, CarModel, Product


class CatalogAjaxTests(TestCase):
    def setUp(self):
        cache.clear()
        self.audi = Brand.objects.create(name='Audi', slug='audi')
        self.bmw = Brand.objects.create(name='BMW', slug='bmw')
        self.a3 = CarModel.objects.create(name='A3', slug='a3', brand=self.audi)
        self.x3 = CarModel.objects.create(name='X3', slug='x3', brand=self.bmw)
        for i in range(6):
            Product.objects.create(title=f'Audi {i}', slug=f'audi-{i}',
                                   brand=self.audi, car_model=self.a3, price=100 + i)
        Product.objects.create(title='BMW X3', slug='bmw', brand=self.bmw,
                               car_model=self.x3, price=200)
        Product.objects.create(title='No model', slug='no-model', brand=self.audi, price=90)
        self.url = reverse('catalog:catalog')

    def test_brand_model_and_price(self):
        response = self.client.get(self.url, {'brand': self.audi.pk, 'model': self.a3.pk,
                                             'price_min': 103})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 3)

    def test_automotive_models_are_ignored_and_brand_filter_still_works(self):
        for model in (self.x3.pk, 'abc', '999999999999999999999999'):
            response = self.client.get(self.url, {'brand': self.audi.pk, 'model': model})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['page_obj'].paginator.count, 7)

    def test_brand_keeps_products_without_model(self):
        response = self.client.get(self.url, {'brand': self.audi.pk})
        self.assertEqual(response.context['page_obj'].paginator.count, 7)

    def test_replacement_contains_controls_and_count(self):
        response = self.client.get(self.url, {'brand': self.bmw.pk}, HTTP_X_CATALOG_MODE='replace')
        self.assertContains(response, 'catalog-filter-form')
        self.assertContains(response, 'BMW X3')
        self.assertNotContains(response, '<html')
        self.assertEqual(response.context['page_obj'].paginator.count, 1)

    def test_append_preserves_brand_and_pagination(self):
        response = self.client.get(self.url, {'brand': self.audi.pk, 'model': self.a3.pk, 'page': 2},
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = response.json()
        self.assertFalse(data['has_next'])
        self.assertIsNone(data['next_page'])
        self.assertIn('Audi 4', data['html'])
        self.assertNotIn('BMW X3', data['html'])
        self.assertNotIn('catalog-filter-form', data['html'])

    def test_direct_second_page_points_to_third(self):
        for i in range(5):
            Product.objects.create(title=f'Extra {i}', slug=f'extra-{i}', price=300)
        response = self.client.get(self.url, {'page': 2})
        self.assertContains(response, 'data-next-page="3"')

    def test_bad_range_is_visible_in_ajax(self):
        response = self.client.get(self.url, {'price_min': 200, 'price_max': 100},
                                   HTTP_X_CATALOG_MODE='replace')
        self.assertContains(response, 'Проверьте диапазон')
        self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_sort_form_keeps_brand_and_availability_but_drops_car_model(self):
        response = self.client.get(self.url, {'brand': self.audi.pk, 'model': self.a3.pk,
                                             'availability': 'in_stock', 'sort': 'price_desc'})
        self.assertNotContains(response, 'name="model"')
        self.assertContains(response, f'name="brand" value="{self.audi.pk}"')
        self.assertContains(response, 'name="availability" value="in_stock"')
        products = list(response.context['products'])
        self.assertEqual(products[0].price, 105)
