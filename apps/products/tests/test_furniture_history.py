"""шаг 16: furniture history order, privacy and session isolation."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.products.constants import MAX_RECENTLY_VIEWED
from apps.products.models import Product
from apps.wishlist.models import Favorite


class FurnitureHistoryTests(TestCase):
    def setUp(self):
        self.first = Product.objects.create(title='Шкаф из дуба', slug='oak-history', price=100, currency='EUR', image='products/original-history.jpg')
        self.second = Product.objects.create(title='Полка', slug='shelf-history', price=200, is_featured=True)
        self.hidden = Product.objects.create(title='Скрытое изделие', slug='private-history', price=1, is_active=False, is_featured=True)
        self.url = reverse('catalog:recently_viewed')

    def history(self, ids):
        session = self.client.session
        session['recently_viewed'] = ids
        session.save()

    def test_order_original_photo_and_furniture_shell_without_changing_history(self):
        ids = [self.first.pk, self.hidden.pk, self.second.pk, 999999]
        self.history(ids)
        response = self.client.get(self.url)
        self.assertEqual(response.context['products'], [self.first, self.second])
        self.assertEqual(self.client.session['recently_viewed'], ids)
        for text in ['Недавно смотрели', 'furniture-reference.css', 'furniture-catalog.css', '/media/products/original-history.jpg', '100 €', 'recently_viewed.js', f'последние {MAX_RECENTLY_VIEWED}']:
            self.assertContains(response, text)
        for text in [self.hidden.title, self.hidden.slug, 'автомобил', 'themes/auto.css', '/thumbs/']:
            self.assertNotContains(response, text)

    def test_product_visits_keep_latest_first_no_duplicates_and_limit(self):
        products = [self.first, self.second] + [Product.objects.create(title=f'Стол {i}', slug=f'visit-{i}', price=1) for i in range(MAX_RECENTLY_VIEWED)]
        for product in products:
            self.assertEqual(self.client.get(product.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.session['recently_viewed'], [p.pk for p in reversed(products[-MAX_RECENTLY_VIEWED:])])
        self.client.get(products[-2].get_absolute_url())
        ids = self.client.session['recently_viewed']
        self.assertEqual(ids[0], products[-2].pk)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([p.pk for p in self.client.get(self.url).context['products']], ids)

    def test_clear_is_post_only_and_keeps_favorites_and_comparison(self):
        self.history([self.first.pk])
        session = self.client.session
        session['wishlist'] = [self.first.pk]
        session['comparison'] = [self.second.pk]
        session.save()
        url = reverse('catalog:clear_recently_viewed_ajax')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).json(), {'success': True, 'count': 0})
        self.assertNotIn('recently_viewed', self.client.session)
        self.assertEqual(self.client.session['wishlist'], [self.first.pk])
        self.assertEqual(self.client.session['comparison'], [self.second.pk])
        self.assertEqual(self.client.get(self.url).context['products'], [])
        self.assertEqual(self.client.post(url).status_code, 200)

    def test_direct_page_csrf_supports_clear_favorite_and_comparison(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.url)
        token = client.cookies['csrftoken'].value
        for url in [reverse('catalog:clear_recently_viewed_ajax'), reverse('wishlist:toggle', args=[self.second.pk]), reverse('catalog:toggle_comparison_ajax', args=[self.second.pk])]:
            self.assertEqual(client.post(url).status_code, 403)
            self.assertEqual(client.post(url, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_empty_recommendations_and_favorite_state_for_guest_and_account(self):
        session = self.client.session
        session['wishlist'] = [self.second.pk]
        session.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'Здесь появятся просмотренные изделия')
        self.assertEqual(response.context['recommended_products'], [self.second])
        self.assertContains(response, 'wishlist-btn active')
        self.assertNotContains(response, self.hidden.title)
        user = get_user_model().objects.create_user('history-client', password='test-only')
        Favorite.objects.create(user=user, product=self.second)
        self.client.force_login(user)
        self.assertContains(self.client.get(self.url), 'wishlist-btn active')

    def test_history_is_separate_between_browsers_and_titles_are_escaped(self):
        self.first.title = '<script>alert(1)</script>'
        self.first.save(update_fields=['title'])
        self.history([self.first.pk])
        response = self.client.get(self.url)
        self.assertNotContains(response, self.first.title)
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertEqual(Client().get(self.url).context['products'], [])
