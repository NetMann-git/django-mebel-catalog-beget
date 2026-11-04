"""шаг 41: home shows published catalog content with original image URLs."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Category, Product
from apps.reviews.models import Review, ReviewImage
from apps.home.furniture_showcase import category_images


class FurnitureHomeShowcaseTests(TestCase):
    def setUp(self):
        self.category=Category.objects.create(title='Шкафы',slug='shkafy')
        self.product=Product.objects.create(title='Шкаф <дуб>',slug='showcase-oak',price=100,
            category=self.category,image='products/original-oak.jpg',is_featured=True)
        self.user=get_user_model().objects.create_user('showcase-author',first_name='Анна')

    def test_real_featured_product_category_photo_and_original_links(self):
        hidden=Product.objects.create(title='Скрытое изделие',slug='showcase-hidden',price=10,
            category=self.category,image='products/hidden.jpg',is_featured=True,is_active=False)
        response=self.client.get(reverse('home'))
        for text in ['Мебель из нашего каталога','Шкаф &lt;дуб&gt;',self.product.get_absolute_url(),
                     '/media/products/original-oak.jpg','furniture-showcase.css','home-callback.js',
                     'id="home-callback-form"','id="portfolio"','id="reviews"','id="faq"']:
            self.assertContains(response,text)
        self.assertNotContains(response,hidden.title)
        self.assertNotContains(response,'/media/products/hidden.jpg')
        self.assertNotContains(response,'<h3>Шкаф <дуб></h3>')
        self.assertEqual(response.context['furniture_category_images']['shkafy'],self.product.image.url)
        self.assertEqual(Product.objects.count(),2)

    def test_only_published_reviews_of_active_products_and_image_priority(self):
        published=Review.objects.create(product=self.product,user=self.user,rating=5,text='Отличная сборка <script>x</script>',is_published=True)
        ReviewImage.objects.create(review=published,image='reviews/original-review.jpg')
        Review.objects.create(product=self.product,rating=2,text='На модерации секрет',is_published=False)
        hidden=Product.objects.create(title='Закрытая мебель',slug='private-reviews',price=10,is_active=False)
        Review.objects.create(product=hidden,rating=5,text='Скрытое изделие отзыв',is_published=True)
        response=self.client.get(reverse('home'))
        self.assertEqual(list(response.context['furniture_reviews']),[published])
        for text in ['Отличная сборка &lt;script&gt;x&lt;/script&gt;','Анна','Оценка 5 из 5','/media/reviews/original-review.jpg']:
            self.assertContains(response,text)
        for text in ['На модерации секрет','Скрытое изделие отзыв','<script>x</script>','Здесь появится отзыв клиента']:
            self.assertNotContains(response,text)

    def test_limits_and_empty_images(self):
        for i in range(6):
            Product.objects.create(title=f'Мебель {i}',slug=f'showcase-{i}',price=100,is_featured=True)
            Review.objects.create(product=self.product,rating=4,text=f'Отзыв {i}',is_published=True)
        response=self.client.get(reverse('home'))
        self.assertContains(response,'class="fm-project-link"',count=4)
        self.assertContains(response,'class="fm-review"',count=3)
        self.assertContains(response,'Фото пока нет')

    def test_empty_site_keeps_reference_examples_and_has_no_fake_reviews(self):
        self.product.is_featured=False;self.product.save(update_fields=['is_featured'])
        response=self.client.get(reverse('home'))
        self.assertContains(response,'Примеры мебельных решений')
        self.assertContains(response,'Изображения из дизайн-макета')
        self.assertContains(response,'Здесь пока нет опубликованных отзывов.')
        self.assertNotContains(response,'Здесь появится отзыв клиента')

    def test_category_photos_use_public_images_and_skip_conflicted_category(self):
        self.product.is_featured=False;self.product.save(update_fields=['is_featured'])
        no_image=Product.objects.create(title='Без фото',slug='no-showcase-photo',category=self.category,price=100,image='')
        self.assertEqual(category_images({'shkafy':'/catalog/?category=1'}),{'shkafy':self.product.image.url})
        self.assertEqual(category_images({}),{})
        self.product.is_active=False;self.product.save(update_fields=['is_active'])
        self.assertEqual(category_images({'shkafy':'/catalog/?category=1'}),{})
