"""шаг 25: prevent disconnecting AJAX widgets from furniture templates."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product, Category, Badge, AttributeType, AttributeValue, ProductAttribute, EquipmentGroup, EquipmentOption
from apps.search.models import SearchQuery


class SmartSearchIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(title='Дубовые шкафы', slug='smart-cases')
        self.product = Product.objects.create(title='Дубовый шкаф', slug='smart-case', price=100, category=self.category)
        self.badge = Badge.objects.create(title='Дубовая коллекция', slug='smart-oak')
        kind = AttributeType.objects.create(name='Материал', slug='smart-material', data_type='choice')
        value = AttributeValue.objects.create(attribute_type=kind, value='Дуб')
        ProductAttribute.objects.create(product=self.product, attribute_type=kind, attribute_value=value)

    def test_search_and_catalog_load_one_widget_with_matching_controls(self):
        for url, control in [(reverse('search:search'), 'furniture-search-suggestions'),
                             (reverse('catalog:catalog'), 'catalog-search-suggestions')]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'data-smart-search-input', count=1)
            self.assertContains(response, f'aria-controls="{control}"', count=1)
            self.assertContains(response, f'id="{control}"', count=1)
            self.assertContains(response, '<script src="/static/search/js/search.js" defer></script>', count=1)
            self.assertContains(response, 'search/css/furniture-smart-search.css', count=1)

    def test_replaced_filter_fragment_keeps_widget_markup(self):
        response = self.client.get(reverse('catalog:catalog'), {'category': self.category.pk}, HTTP_X_CATALOG_MODE='replace')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-smart-search-input', count=1)
        self.assertContains(response, 'id="catalog-search-suggestions"', count=1)
        self.assertNotContains(response, '<script')

    def test_suggestions_retain_all_result_types_and_popular_queries(self):
        response = self.client.get(reverse('search:suggest'), {'q': 'Дуб'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        self.assertEqual({row['type'] for row in results}, {'product', 'category', 'badge', 'attribute'})
        self.assertTrue(any(row['type'] == 'attribute' and row['url'] == self.product.get_absolute_url() for row in results))
        SearchQuery.objects.create(query='Шкаф', count=5)
        self.assertIn('Шкаф', self.client.get(reverse('search:popular')).json()['popular'])

    def test_catalog_results_and_suggestions_match_words_across_public_fields(self):
        self.product.title = 'Шкаф с тёмным фасадом'
        self.product.article = 'F-204'
        self.product.save()
        group = EquipmentGroup.objects.create(name='Фурнитура', slug='smart-fittings')
        option = EquipmentOption.objects.create(name='Доводчики', group=group)
        self.product.equipment.add(option)
        for query in ('ФАСАДОМ  шкаф', 'темным, дуб', 'шкаф доводчики', 'f-204', 'шкафы дуб'):
            with self.subTest(query=query):
                catalog = self.client.get(reverse('catalog:catalog'), {'q': query})
                search = self.client.get(reverse('search:search'), {'query': query})
                suggestions = self.client.get(reverse('search:suggest'), {'q': query}).json()['results']
                self.assertEqual(list(catalog.context['products']), [self.product])
                self.assertEqual(list(search.context['search_results']), [self.product])
                self.assertEqual([row['id'] for row in suggestions if row['type'] == 'product'], [self.product.pk])

        option.is_active = False
        option.save()
        search = self.client.get(reverse('search:search'), {'query': 'шкаф доводчики'})
        self.assertEqual(list(search.context['search_results']), [])

    def test_exact_title_ranks_first_and_unpublished_rows_disappear_from_suggestions(self):
        other = Product.objects.create(
            title='Аксессуар', description='Дубовый шкаф', slug='smart-accessory', price=10,
        )
        query = {'q': 'дубовый шкаф'}
        url = reverse('search:suggest')
        response = self.client.get(url, query).json()['results']
        self.assertEqual([row['id'] for row in response if row['type'] == 'product'], [self.product.pk, other.pk])
        self.product.is_active = False
        self.product.save()
        response = self.client.get(url, query).json()['results']
        self.assertNotIn(self.product.get_absolute_url(), [row['url'] for row in response])
