"""шаг 47: public review list publication, pagination, and escaping."""
from django.test import TestCase
from django.urls import reverse, resolve
from apps.products.models import Product
from apps.reviews.models import Review, ReviewReply, ReviewImage


class FurnitureReviewsTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='Шкаф', slug='review-case', price=100)
        self.url = reverse('furniture_reviews')

    def review(self, **kwargs):
        return Review.objects.create(product=self.product, rating=5, text='Хорошая работа',
                                     **{'is_published': True, **kwargs})

    def test_only_published_reviews_of_active_products_and_no_private_data(self):
        visible = self.review(guest_name='Покупатель', title='Открытый отзыв')
        self.review(guest_name='Секретный автор', is_published=False)
        hidden = Product.objects.create(title='Скрытый шкаф', slug='hidden-case', price=100, is_active=False)
        Review.objects.create(product=hidden, rating=4, text='Скрытый текст', is_published=True)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Открытый отзыв')
        self.assertNotContains(response, 'Секретный автор')
        self.assertNotContains(response, 'Скрытый текст')
        self.assertNotContains(response, 'Скрытый шкаф')
        self.assertContains(response, self.product.get_absolute_url())
        self.assertEqual(list(response.context['page_obj']), [visible])

    def test_photos_replies_and_escaping(self):
        review = self.review(guest_name='<script>bad()</script>', title='<b>Заголовок</b>')
        ReviewImage.objects.create(review=review, image='reviews/original.jpg')
        ReviewReply.objects.create(review=review, text='<script>reply()</script>')
        response = self.client.get(self.url)
        for text in ['&lt;script&gt;bad()', '&lt;b&gt;Заголовок', '&lt;script&gt;reply()',
                     '/media/reviews/original.jpg', 'Ответ мастерской']:
            self.assertContains(response, text)
        self.assertNotContains(response, '<script>bad()')
        self.assertNotContains(response, '<script>reply()')

    def test_pagination_is_stable_and_complete(self):
        reviews = [self.review(guest_name=str(i)) for i in range(13)]
        first = self.client.get(self.url)
        second = self.client.get(self.url + '?page=2')
        self.assertEqual(list(first.context['page_obj']), list(reversed(reviews))[:12])
        self.assertEqual(list(second.context['page_obj']), reviews[:1])
        self.assertContains(first, '?page=2')
        self.assertContains(second, '?page=1')
        for value in ['bad', '0', '999']:
            self.assertEqual(self.client.get(self.url + '?page=' + value).status_code, 200)

    def test_empty_page_has_no_fabricated_reviews(self):
        self.assertContains(self.client.get(self.url), 'Пока нет опубликованных отзывов')

    def test_links_sitemap_and_existing_review_routes(self):
        self.assertContains(self.client.get('/'), 'href="' + self.url + '"', count=3)
        self.assertContains(self.client.get('/sitemap-pages.xml'), self.url)
        self.assertEqual(resolve(reverse('reviews:add_review', args=[self.product.pk])).url_name, 'add_review')
