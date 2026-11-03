"""шаг 34: personal review visibility and safe furniture rendering."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product
from apps.reviews.models import Review


class FurniturePersonalReviewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('review-owner')
        self.other = get_user_model().objects.create_user('review-other')
        self.product = Product.objects.create(title='Шкаф <дуб>', slug='review-case', price=100)
        self.url = reverse('users:reviews')

    def test_only_own_reviews_including_unpublished_are_shown_and_escaped(self):
        own = Review.objects.create(user=self.user, product=self.product, rating=4,
                                    title='<script>title</script>', text='<script>alert(1)</script>', is_published=False)
        Review.objects.create(user=self.other, product=self.product, rating=5, text='Чужой приватный отзыв')
        Review.objects.create(product=self.product, rating=5, text='Гостевой отзыв')
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['reviews']), [own])
        for text in ['furniture-reviews.css', 'noindex, nofollow', 'Оценка 4 из 5',
                     '&lt;script&gt;title&lt;/script&gt;', '&lt;script&gt;alert(1)&lt;/script&gt;',
                     'Шкаф &lt;дуб&gt;', self.product.get_absolute_url(), reverse('users:dashboard')]:
            self.assertContains(response, text)
        for text in ['<script>title', 'Чужой приватный отзыв', 'Гостевой отзыв', 'themes/auto.css']:
            self.assertNotContains(response, text)
        self.assertEqual(Review.objects.count(), 3)

    def test_empty_state_does_not_show_other_users_reviews(self):
        Review.objects.create(user=self.other, product=self.product, rating=3, text='Не мой отзыв')
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, 'Вы ещё не оставляли отзывы.')
        self.assertContains(response, reverse('catalog:catalog'))
        self.assertNotContains(response, 'Не мой отзыв')

    def test_guest_must_login(self):
        response = self.client.get(self.url, follow=True)
        self.assertEqual(response.redirect_chain, [(reverse('users:login') + '?next=' + self.url, 302)])
        self.assertEqual(response.status_code, 200)
