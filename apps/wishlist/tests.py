"""шаг 14: public wishlist privacy, saved references and action contracts."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.products.models import Product
from .models import Favorite


class FurnitureWishlistTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('client', password='test-only')
        self.other = get_user_model().objects.create_user('other', password='test-only')
        self.item = Product.objects.create(title='Шкаф из дуба', slug='oak-wardrobe', price=100, currency='EUR', image='products/original.jpg')
        self.hidden = Product.objects.create(title='Неопубликованная мебель', slug='private-draft', price=200, is_active=False)
        self.url = reverse('wishlist:list')

    def guest_ids(self, ids):
        session = self.client.session
        session['wishlist'] = ids
        session.save()

    def test_guest_page_uses_original_furniture_card_and_keeps_missing_references(self):
        self.guest_ids([self.item.pk, self.hidden.pk, 999999])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['products'], [self.item])
        self.assertEqual(response.context['wishlist_count'], 1)
        for text in ['Избранная мебель', 'furniture-wishlist.css', 'fc-card', '/media/products/original.jpg', '100 €', 'сессией браузера', 'width=device-width']:
            self.assertContains(response, text)
        for text in [self.hidden.title, self.hidden.slug, 'автомобил', 'themes/auto.css', '/thumbs/']:
            self.assertNotContains(response, text)
        self.assertEqual(self.client.session['wishlist'], [self.item.pk, self.hidden.pk, 999999])

    def test_authenticated_page_hides_drafts_without_deleting_saved_records(self):
        self.client.force_login(self.user)
        saved = Favorite.objects.create(user=self.user, product=self.item)
        draft = Favorite.objects.create(user=self.user, product=self.hidden)
        response = self.client.get(self.url)
        self.assertEqual(response.context['products'], [self.item])
        self.assertEqual(response.context['wishlist_count'], 1)
        self.assertNotContains(response, self.hidden.title)
        self.assertNotContains(response, self.hidden.slug)
        self.assertEqual(set(Favorite.objects.filter(user=self.user).values_list('pk', flat=True)), {saved.pk, draft.pk})
        self.hidden.is_active = True
        self.hidden.save(update_fields=['is_active'])
        response = self.client.get(self.url)
        self.assertEqual(response.context['products'], [self.hidden, self.item])
        self.assertEqual(response.context['wishlist_count'], 2)

    def test_empty_page_and_recommendations_exclude_unpublished_items(self):
        self.hidden.is_featured = True
        self.hidden.save(update_fields=['is_featured'])
        self.assertContains(self.client.get(self.url), 'Сохраните понравившуюся мебель')
        self.item.is_featured = True
        self.item.save(update_fields=['is_featured'])
        response = self.client.get(self.url)
        self.assertEqual(response.context['recommended_products'], [self.item])
        self.assertContains(response, 'recommended-section')
        self.assertContains(response, 'fc-card')
        self.assertNotContains(response, self.hidden.title)

    def test_accounts_have_separate_saved_lists_and_clear_only_owns_records(self):
        Favorite.objects.create(user=self.other, product=self.item)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).context['products'], [])
        Favorite.objects.create(user=self.user, product=self.item)
        self.assertEqual(self.client.get(reverse('wishlist:clear')).status_code, 405)
        self.assertTrue(self.client.post(reverse('wishlist:clear')).json()['success'])
        self.assertFalse(Favorite.objects.filter(user=self.user).exists())
        self.assertTrue(Favorite.objects.filter(user=self.other).exists())

    def test_guest_toggle_counts_only_visible_products_and_preserves_other_session_data(self):
        self.guest_ids([self.hidden.pk, 999999])
        session = self.client.session
        session['comparison'] = [self.item.pk]
        session.save()
        url = reverse('wishlist:toggle', args=[self.item.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).json(), {'is_favorite': True, 'count': 1})
        self.assertEqual(self.client.post(url).json(), {'is_favorite': False, 'count': 0})
        self.assertEqual(self.client.session['wishlist'], [self.hidden.pk, 999999])
        self.assertEqual(self.client.post(reverse('wishlist:toggle', args=[self.hidden.pk])).status_code, 404)
        self.client.post(reverse('wishlist:clear'))
        self.assertEqual(self.client.session['wishlist'], [])
        self.assertEqual(self.client.session['comparison'], [self.item.pk])

    def test_user_toggle_counter_matches_visible_page(self):
        self.client.force_login(self.user)
        Favorite.objects.create(user=self.user, product=self.hidden)
        url = reverse('wishlist:toggle', args=[self.item.pk])
        self.assertEqual(self.client.post(url).json(), {'is_favorite': True, 'count': 1})
        self.assertEqual(self.client.get(self.url).context['wishlist_count'], 1)
        self.assertEqual(self.client.post(url).json(), {'is_favorite': False, 'count': 0})
        self.assertTrue(Favorite.objects.filter(user=self.user, product=self.hidden).exists())

    def test_direct_wishlist_issues_csrf_and_actions_require_it(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.url)
        token = client.cookies['csrftoken'].value
        for url in [reverse('wishlist:toggle', args=[self.item.pk]), reverse('wishlist:clear')]:
            self.assertEqual(client.post(url).status_code, 403)
            self.assertEqual(client.post(url, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_catalog_counter_omits_unpublished_saved_products(self):
        self.guest_ids([self.item.pk, self.hidden.pk, 999999])
        response = self.client.get(reverse('catalog:catalog'))
        self.assertEqual(response.context['wishlist_count'], 1)
        self.assertContains(response, 'В избранном')
