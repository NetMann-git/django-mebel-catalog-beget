"""шаг 15: furniture comparison keeps public data and selection contracts."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.products.constants import MAX_COMPARISON_ITEMS
from apps.products.models import Product, Category, AttributeType, AttributeValue, ProductAttribute
from apps.wishlist.models import Favorite


class FurnitureComparisonTests(TestCase):
    def setUp(self):
        category = Category.objects.create(title='Шкафы', slug='shkafy')
        self.first = Product.objects.create(title='Шкаф из дуба', slug='oak-case', price=120000, currency='EUR', category=category, article='F-001', image='products/original-case.jpg')
        self.second = Product.objects.create(title='Полка', slug='shelf', price=15000, currency='USD', is_featured=True)
        self.hidden = Product.objects.create(title='Скрытый проект', slug='private-project', price=1, is_active=False, is_featured=True)
        self.kind = AttributeType.objects.create(name='Материал', slug='material')
        value = AttributeValue.objects.create(attribute_type=self.kind, value='Дуб')
        ProductAttribute.objects.create(product=self.first, attribute_type=self.kind, attribute_value=value)
        self.url = reverse('catalog:comparison')

    def select(self, ids):
        session = self.client.session
        session['comparison'] = ids
        session.save()

    def test_shell_original_photo_currencies_and_attributes(self):
        self.select([self.first.pk, self.second.pk])
        response = self.client.get(self.url)
        for text in ['Сравнение мебели', 'furniture-comparison.css', '/media/products/original-case.jpg', '120\u00a0000 €', '15\u00a0000 $', 'Материал', 'Дуб', 'F-001', 'Фото пока нет', 'tabindex="0"', f'до {MAX_COMPARISON_ITEMS} изделий']:
            self.assertContains(response, text)
        for text in ['автомобил', '/thumbs/', 'themes/auto.css', 'logo.png']:
            self.assertNotContains(response, text)
        rows = response.context['attributes_rows']
        self.assertEqual(rows[0][self.first.pk], 'Дуб')
        self.assertEqual(rows[0][self.second.pk], '—')
        self.assertContains(response, reverse('catalog:toggle_comparison_ajax', args=[self.first.pk]))

    def test_order_and_hidden_references_retained_without_exposure(self):
        ids = [self.second.pk, self.hidden.pk, self.first.pk, 999999]
        self.select(ids)
        response = self.client.get(self.url)
        self.assertEqual(response.context['products'], [self.second, self.first])
        self.assertNotContains(response, self.hidden.title)
        self.assertNotContains(response, self.hidden.slug)
        self.assertEqual(self.client.session['comparison'], ids)

    def test_empty_state_and_recommendations_keep_furniture_cards(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Какую мебель сравним?')
        self.assertEqual(response.context['recommended_products'], [self.second])
        self.assertContains(response, 'fc-card')
        self.assertNotContains(response, self.hidden.title)
        self.assertEqual(response.context['comparison_limit'], MAX_COMPARISON_ITEMS)

    def test_recommendation_favorites_state_for_guest_and_user(self):
        session = self.client.session
        session['wishlist'] = [self.second.pk]
        session.save()
        self.assertContains(self.client.get(self.url), 'wishlist-btn active')
        user = get_user_model().objects.create_user('furniture-client', password='test-only')
        Favorite.objects.create(user=user, product=self.second)
        self.client.force_login(user)
        self.assertContains(self.client.get(self.url), 'wishlist-btn active')

    def test_direct_page_issues_csrf_for_comparison_and_favorites(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.url)
        token = client.cookies['csrftoken'].value
        for url in [reverse('catalog:toggle_comparison_ajax', args=[self.first.pk]), reverse('wishlist:toggle', args=[self.first.pk])]:
            self.assertEqual(client.post(url).status_code, 403)
            self.assertEqual(client.post(url, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_toggle_limit_remove_and_reject_draft(self):
        products = [self.first, self.second]
        products += [Product.objects.create(title=f'Изделие {i}', slug=f'item-{i}', price=100) for i in range(MAX_COMPARISON_ITEMS - 1)]
        for product in products[:MAX_COMPARISON_ITEMS]:
            response = self.client.post(reverse('catalog:toggle_comparison_ajax', args=[product.pk]))
            self.assertTrue(response.json()['is_added'])
        over_limit = reverse('catalog:toggle_comparison_ajax', args=[products[-1].pk])
        self.assertEqual(self.client.post(over_limit).status_code, 400)
        self.assertEqual(len(self.client.session['comparison']), MAX_COMPARISON_ITEMS)
        url = reverse('catalog:toggle_comparison_ajax', args=[self.first.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url).json()
        self.assertFalse(response['is_added'])
        self.assertEqual(response['count'], MAX_COMPARISON_ITEMS - 1)
        self.assertEqual(self.client.post(reverse('catalog:toggle_comparison_ajax', args=[self.hidden.pk])).status_code, 404)

    def test_escaped_titles_and_attribute_values(self):
        self.first.title = '<script>private()</script>'
        self.first.save(update_fields=['title'])
        value = self.first.attributes.get().attribute_value
        value.value = '<img src=x onerror=alert(1)>'
        value.save(update_fields=['value'])
        self.select([self.first.pk])
        response = self.client.get(self.url)
        self.assertNotContains(response, self.first.title)
        self.assertNotContains(response, value.value)
        self.assertContains(response, '&lt;script&gt;private()&lt;/script&gt;')

    def test_sessions_are_independent_and_last_removal_gives_empty_page(self):
        self.select([self.first.pk])
        self.assertEqual(Client().get(self.url).context['products'], [])
        self.client.post(reverse('catalog:toggle_comparison_ajax', args=[self.first.pk]))
        response = self.client.get(self.url)
        self.assertEqual(response.context['products'], [])
        self.assertEqual(self.client.session['comparison'], [])
