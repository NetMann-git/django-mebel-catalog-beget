"""шаг 32: account favorites reuse wishlist behavior and publication rules."""
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.products.models import Product
from apps.wishlist.models import Favorite


class FurnitureAccountFavoritesTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user('favorites-owner', password='test-only')
        self.other = users.objects.create_user('favorites-other', password='test-only')
        self.product = Product.objects.create(title='Шкаф из дуба', slug='account-oak-case', price=100,
                                              image='products/original-account-oak.jpg')
        self.hidden = Product.objects.create(title='Неопубликованный секрет', slug='account-private-case', price=10, is_active=False)
        self.foreign = Product.objects.create(title='Чужое сохранение', slug='foreign-favorite', price=200)
        Favorite.objects.create(user=self.user, product=self.product)
        Favorite.objects.create(user=self.user, product=self.hidden)
        Favorite.objects.create(user=self.other, product=self.foreign)
        self.url = reverse('users:favorites')
        self.client.force_login(self.user)

    def test_account_and_public_wishlist_have_same_published_selection_and_actions(self):
        account = self.client.get(self.url)
        public = self.client.get(reverse('wishlist:list'))
        self.assertEqual(account.status_code, 200)
        self.assertEqual([p.pk for p in account.context['products']], [self.product.pk])
        self.assertEqual([p.pk for p in account.context['products']], [p.pk for p in public.context['products']])
        self.assertEqual(account.context['wishlist_ids'], [self.product.pk])
        for text in ['furniture-wishlist.css', '/media/products/original-account-oak.jpg',
                     'id="wishlist-products"', 'id="clear-wishlist"', 'В избранном',
                     reverse('catalog:comparison'), reverse('users:dashboard')]:
            self.assertContains(account, text)
        for product in [self.hidden, self.foreign]:
            self.assertNotContains(account, product.title)
            self.assertNotContains(account, product.get_absolute_url())
        self.assertEqual(Favorite.objects.count(), 3)
        self.assertEqual(self.client.get(reverse('users:dashboard')).context['favorites_count'], 1)

    def test_guest_still_has_to_login_for_account_url(self):
        client = Client()
        response = client.get(self.url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[0][0], reverse('users:login') + '?next=' + self.url)
        self.assertNotContains(response, self.product.title)

    def test_unpublishing_keeps_reference_and_republishing_restores_item(self):
        self.product.is_active = False
        self.product.save(update_fields=['is_active'])
        response = self.client.get(self.url)
        self.assertEqual(response.context['products'], [])
        self.assertContains(response, 'Сохраните понравившуюся мебель')
        self.assertEqual(self.client.get(reverse('users:dashboard')).context['favorites_count'], 0)
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 2)
        self.product.is_active = True
        self.product.save(update_fields=['is_active'])
        self.assertEqual([p.pk for p in self.client.get(self.url).context['products']], [self.product.pk])

    def test_existing_recommendations_are_retained(self):
        with patch('apps.wishlist.views.RecommendationService.get_similar_products', return_value=[self.foreign]) as recommend:
            response = self.client.get(self.url)
        self.assertEqual(response.context['recommended_products'], [self.foreign])
        self.assertContains(response, 'Возможно, вам понравится')
        self.assertContains(response, self.foreign.title)
        self.assertEqual(recommend.call_args.kwargs['page'], 'wishlist')

    def test_toggle_and_clear_use_existing_csrf_endpoints_and_only_own_records(self):
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        token = client.cookies['csrftoken'].value
        toggle = reverse('wishlist:toggle', args=[self.product.pk])
        self.assertEqual(client.post(toggle).status_code, 403)
        response = client.post(toggle, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['is_favorite'])
        self.assertEqual(response.json()['count'], 0)
        self.assertTrue(Favorite.objects.filter(user=self.other, product=self.foreign).exists())
        self.assertEqual(client.post(toggle, HTTP_X_CSRFTOKEN=token).status_code, 200)
        clear = reverse('wishlist:clear')
        self.assertEqual(client.post(clear).status_code, 403)
        self.assertEqual(client.post(clear, HTTP_X_CSRFTOKEN=token).json(), {'success': True, 'count': 0})
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 0)
        self.assertTrue(Favorite.objects.filter(user=self.other, product=self.foreign).exists())
