"""шаг 24: public search rendering and existing search/action contracts."""
from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from apps.products.models import Product, Category
from apps.wishlist.models import Favorite


class FurnitureSearchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('search:search')
        self.category = Category.objects.create(title='Шкафы', slug='search-cases')
        self.product = Product.objects.create(title='Шкаф из дуба', slug='search-oak-case',
            article='OAK-24', short_description='Короткое описание', description='Полное описание',
            price=120000, image='products/original-search.jpg', category=self.category)
        self.hidden = Product.objects.create(title='Шкаф скрытый', slug='search-hidden-case',
            price=1, is_active=False, article='PRIVATE-24')

    def test_empty_and_whitespace_queries_show_form_without_results(self):
        for query in ['', '   ']:
            response = self.client.get(self.url, {'query': query})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Расскажите, какую мебель ищете')
            self.assertContains(response, 'action="/search/"')
            self.assertNotContains(response, self.product.get_absolute_url())

    def test_existing_search_fields_return_only_published_furniture(self):
        for query in ['Шкаф', 'шкаф', 'ШКАФ', 'OAK-24', 'oak-24', 'Короткое', 'короткое', 'Полное', 'полное']:
            response = self.client.get(self.url, {'query': query})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(response.context['search_results']), [self.product])
            for text in ['Поиск мебели', 'furniture-search.css', 'furniture-reference.css',
                         self.product.get_absolute_url(), '/media/products/original-search.jpg',
                         'name="robots" content="noindex, follow"', 'name="viewport"']:
                self.assertContains(response, text)
            self.assertNotContains(response, self.hidden.title)
            self.assertNotContains(response, self.hidden.get_absolute_url())
            self.assertNotContains(response, 'themes/auto.css')
        self.assertEqual(Product.objects.count(), 2)

    def test_empty_result_and_escaped_query(self):
        query = '<script>alert("x")</script>'
        response = self.client.get(self.url, {'query': query})
        self.assertContains(response, 'Ничего не найдено')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, query)
        self.assertContains(response, 'href="/catalog/"')

    def test_pagination_preserves_query_and_handles_invalid_page(self):
        query = 'Стол & полка'
        items = [Product.objects.create(title=f'{query} {i:02}', slug=f'search-table-{i}', price=10) for i in range(12)]
        first = self.client.get(self.url, {'query': query})
        self.assertEqual(list(first.context['search_results']), items[:10])
        self.assertContains(first, urlencode({'query': query}).replace('+', '%20') + '&amp;page=2')
        second = self.client.get(self.url, {'query': query, 'page': 2})
        self.assertEqual(list(second.context['search_results']), items[10:])
        for page, expected in [('invalid', 1), ('999', 2)]:
            response = self.client.get(self.url, {'query': query, 'page': page})
            self.assertEqual(response.context['search_results'].number, expected)

    def test_guest_buttons_have_state_and_work_with_csrf(self):
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session['wishlist'] = [self.product.pk]
        session['comparison'] = [self.product.pk]
        session.save()
        response = client.get(self.url, {'query': 'OAK-24'})
        self.assertContains(response, 'В избранном')
        self.assertContains(response, 'compare-btn active')
        url = reverse('wishlist:toggle', args=[self.product.pk])
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(client.post(url, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 200)
        self.assertNotIn(self.product.pk, client.session.get('wishlist', []))

    def test_signed_in_favorites_are_scoped_to_user(self):
        users = get_user_model()
        owner = users.objects.create_user('search-owner', password='test-only')
        other = users.objects.create_user('search-other', password='test-only')
        Favorite.objects.create(user=owner, product=self.product)
        self.client.force_login(other)
        self.assertNotContains(self.client.get(self.url, {'query': 'OAK-24'}), 'В избранном')
        self.client.force_login(owner)
        self.assertContains(self.client.get(self.url, {'query': 'OAK-24'}), 'В избранном')

    def test_suggestion_and_popular_endpoints_remain_available(self):
        response = self.client.get(reverse('search:suggest'), {'q': 'Шкаф'})
        self.assertEqual(response.status_code, 200)
        urls = [row.get('url') for row in response.json()['results']]
        self.assertIn(self.product.get_absolute_url(), urls)
        self.assertNotIn(self.hidden.get_absolute_url(), urls)
        self.assertEqual(self.client.get(reverse('search:popular')).status_code, 200)
