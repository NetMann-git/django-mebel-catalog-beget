"""Removed routes and automotive query parameters cannot affect the furniture site."""
import re
from urllib.parse import parse_qs, urlsplit
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, reverse
from apps.products.filters import CatalogFilter
from apps.products.models import AttributeType, AttributeValue, Brand, CarModel, Category, Product, ProductAttribute


class FurnitureLegacyCleanupTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(title='Шкафы', slug='shkafy')
        self.brand = Brand.objects.create(name='Мастерская', slug='workshop')
        self.car = CarModel.objects.create(name='Старая модель', slug='old-car', brand=self.brand)
        for index in range(8):
            Product.objects.create(title=f'Шкаф {index}', slug=f'case-cleanup-{index}', price=100+index,
                                   category=self.category, brand=self.brand, car_model=self.car if index == 0 else None)
        self.product = Product.objects.first()
        kind = AttributeType.objects.create(name='Год из старых данных', slug='year')
        self.year = AttributeValue.objects.create(attribute_type=kind, value='2021')
        ProductAttribute.objects.create(product=self.product, attribute_type=kind, attribute_value=self.year)
        Product.objects.create(title='Скрытый шкаф', slug='private-case', price=1, is_active=False)
        self.legacy = {'model': 'bad', 'year': '2021', 'year_min': 'bad', 'year_max': '0',
                       'fuel_type': 'bad', 'mileage_min': '100', 'mileage_max': '0',
                       'engine_volume_min': '99', 'engine_volume_max': '0', 'power_min': 'bad',
                       'power_max': '0', 'transmission': 'auto', 'drive': 'AWD', 'condition': 'used'}
        self.url = reverse('catalog:catalog')

    def test_legacy_parameters_cannot_filter_catalog_or_trigger_validation(self):
        params = dict(self.legacy, sort='year_desc')
        for headers in [{}, {'HTTP_X_CATALOG_MODE': 'replace'}, {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}]:
            response = self.client.get(self.url, params, **headers)
            self.assertEqual(response.status_code, 200)
            if headers.get('HTTP_X_REQUESTED_WITH'):
                self.assertEqual(response.json()['has_next'], True)
                self.assertNotIn('Скрытый шкаф', response.json()['html'])
            else:
                self.assertEqual(response.context['page_obj'].paginator.count, 8)
                self.assertFalse(response.context['filter_errors'])
                self.assertEqual(response.context['selected_sort'], '')
                self.assertFalse(response.context['furniture_has_filters'])
        self.assertEqual(len(CatalogFilter(params).apply(Product.objects.filter(is_active=True))), 8)

    def test_supported_filters_and_links_remain_independent_of_legacy(self):
        params = dict(self.legacy, q='ШКАФ', category=str(self.category.pk), brand=str(self.brand.pk),
                      price_min='101', availability='in_stock', sort='price_desc', tracking='ignored')
        response = self.client.get(self.url, params)
        self.assertEqual(response.context['page_obj'].paginator.count, 7)
        self.assertEqual([p.price for p in response.context['products']], [107,106,105,104])
        query = parse_qs(response.context['query_params'])
        self.assertEqual(set(query), {'q','category','brand','price_min','availability','sort'})
        soup = BeautifulSoup(response.content, 'html.parser')
        for element in soup.select('input[name]'):
            self.assertNotIn(element['name'], self.legacy)
            self.assertNotEqual(element['name'], 'tracking')
        for link in soup.select('.filter-chip, .fc-pagination a'):
            keys = parse_qs(urlsplit(link.get('href','')).query)
            self.assertFalse(set(keys) & set(self.legacy))
            self.assertNotIn('tracking', keys)
        self.assertEqual(dict(response.context['furniture_extra_filters']), {'brand':str(self.brand.pk),'availability':'in_stock'})

    def test_no_car_or_attribute_lookup_sql_on_cold_or_warm_catalog(self):
        for params in [{}, dict(self.legacy, sort='year_desc')]:
            for warm in [False, True]:
                if not warm:
                    cache.clear()
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(self.url, params)
                self.assertEqual(response.status_code, 200)
                for query in queries:
                    self.assertIsNone(re.search(r'\b(?:from|join)\s+["`]?products_(?:carmodel|attributevalue|productattribute)\b', query['sql'], re.I), query['sql'])
                for key in ['catalog_years','fuel_values','catalog_models','selected_model','selected_year','selected_fuel_type']:
                    self.assertNotIn(key, response.context)

    def test_old_sections_are_not_routed_and_gets_preserve_stored_data(self):
        before = list(Product.objects.values()), list(CarModel.objects.values()), list(AttributeValue.objects.values())
        paths = ['/calculator/util-sbor/','/calculator/rastamozhka/','/size-helper/',
                 '/size-helper/recommend/','/size-helper/table/','/size-helper/helper/']
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.post(path, {'product_id':self.product.pk}).status_code, 404)
        for name in ['calculator:utilization_fee','calculator:customs_clearance','size_helper:form']:
            with self.assertRaises(NoReverseMatch):
                reverse(name)
        after = list(Product.objects.values()), list(CarModel.objects.values()), list(AttributeValue.objects.values())
        self.assertEqual(before, after)
        for path in ['/',self.url,'/services/','/materials/','/contacts/']:
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_invalid_ids_and_price_do_not_break_view_and_editing_remains(self):
        for value in ['abc','999999999999999999999999999','-1','١٢٣']:
            response = self.client.get(self.url, {'category':value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['page_obj'].paginator.count, 0)
        for lower, upper in [('200','100'),('NaN',''),('Infinity',''),('-1','')]:
            response = self.client.get(self.url, {'price_min':lower,'price_max':upper})
            self.assertTrue(response.context['filter_errors'])
        manager = get_user_model().objects.create_user('cleanup-manager')
        manager.profile.role = 'manager'
        manager.profile.save()
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('catalog:product_edit', args=[self.product.pk])).status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(ProductAttribute.objects.filter(attribute_value=self.year).count(), 1)
