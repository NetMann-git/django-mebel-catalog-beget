from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote
from bs4 import BeautifulSoup
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.products.image_variants import image_variant, IMAGE_SIZES
from apps.products.models import Category, Product, ProductGalleryImage
from apps.reviews.models import Review, ReviewImage


class ImageVariantTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = self.settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.category = Category.objects.create(title='Шкафы', slug='shkafy')
        self.product = Product.objects.create(title='Шкаф', slug='image-size-check', price=100, category=self.category, is_featured=True)
        data = BytesIO()
        Image.new('RGB', (4000, 3000), '#a18261').save(data, 'JPEG', quality=97)
        self.original = data.getvalue()
        self.category.image.save('category.jpg', ContentFile(self.original))
        self.product.image.save('product.jpg', ContentFile(self.original))
        self.photo = ProductGalleryImage.objects.create(product=self.product, image=self.product.image.name)
        self.second = ProductGalleryImage.objects.create(product=self.product)
        self.second.image.save('detail.jpg', ContentFile(self.original))
        review = Review.objects.create(product=self.product, rating=5, text='Отзыв', is_published=True)
        self.review_photo = ReviewImage.objects.create(review=review)
        self.review_photo.image.save('review.jpg', ContentFile(self.original))
        manager = get_user_model().objects.create_user('variant-manager')
        manager.profile.role = 'manager'
        manager.profile.save()
        self.client.force_login(manager)

    def dimensions(self, url):
        if url.startswith('/media/'):
            path = Path(self.media.name) / unquote(url[len('/media/'):])
        else:
            path = finders.find(url.split('/static/', 1)[-1])
        with Image.open(path) as image:
            return image.size

    def test_real_dimensions_weight_cache_and_original_bytes(self):
        for preset in IMAGE_SIZES:
            with self.subTest(preset=preset):
                url = image_variant(self.category.image, preset)
                self.assertNotEqual(url, self.category.image.url)
                width, height = self.dimensions(url)
                maximum = IMAGE_SIZES[preset]
                self.assertLessEqual(width, maximum[0])
                self.assertLessEqual(height, maximum[1])
                path = Path(self.media.name) / url[len('/media/'):]
                self.assertLess(path.stat().st_size, len(self.original))
                self.assertEqual(url, image_variant(self.category.image, preset))
        self.assertEqual(Path(self.category.image.path).read_bytes(), self.original)
        self.assertEqual(Path(self.product.image.path).read_bytes(), self.original)

    def test_actual_page_images_use_display_files_full_urls_only_in_links_or_data(self):
        checks = [
            (reverse('catalog:category_list_manage'), '.fm-categories__thumbnail', (192, 128)),
            (reverse('catalog:category_edit', args=[self.category.pk]), '.fm-categories__preview img', (960, 720)),
            ('/', '#categories .fm-category img', (640, 580)),
            ('/', '.fm-showcase-image', (800, 600)),
            ('/', '.fm-review-image', (320, 240)),
            (reverse('catalog:catalog'), '.fc-card-image img', (800, 600)),
            (reverse('catalog:product_list_manage'), '.fm-manage__photo img', (224, 168)),
            (self.product.get_absolute_url(), '#main-image', (1200, 1000)),
            (self.product.get_absolute_url(), '.gallery-thumb-vertical', (160, 120)),
            (self.product.get_absolute_url(), '.review-image-thumb', (320, 240)),
        ]
        originals = {self.product.image.url, self.category.image.url, self.second.image.url, self.review_photo.image.url}
        for url, selector, size in checks:
            with self.subTest(url=url, selector=selector):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                soup = BeautifulSoup(response.content, 'html.parser')
                images = soup.select(selector)
                self.assertTrue(images)
                for image in images:
                    self.assertNotIn(image.get('src'), originals)
                    width, height = self.dimensions(image['src'])
                    self.assertLessEqual(width, size[0])
                    self.assertLessEqual(height, size[1])
        soup = BeautifulSoup(self.client.get(self.product.get_absolute_url()).content, 'html.parser')
        self.assertEqual(soup.select_one('#main-image')['data-full'], self.product.image.url)
        self.assertEqual(soup.select_one('.review-image-link')['href'], self.review_photo.image.url)
        for thumb in soup.select('.gallery-thumb-vertical'):
            self.assertNotEqual(thumb['src'], thumb['data-full'])
            self.assertNotEqual(thumb['data-preview'], thumb['data-full'])

    def test_default_category_variants_small_images_and_missing_source(self):
        self.category.image = ''
        self.category.save()
        url = image_variant(self.category.display_image_url, 'category_table')
        self.assertEqual(self.dimensions(url), (192, 128))
        self.assertIn('-variant-category_table.webp', url)
        self.product.image = 'missing.jpg'
        self.assertIn('image-unavailable.svg', image_variant(self.product.image, 'card'))
        data = BytesIO()
        Image.new('RGB', (50, 40), 'white').save(data, 'PNG')
        self.product.image.save('tiny.png', ContentFile(data.getvalue()))
        self.assertEqual(self.dimensions(image_variant(self.product.image, 'table')), (50, 40))
        with override_settings(STATIC_URL='/assets/'):
            self.assertTrue(image_variant(self.category.display_image_url, 'category_table').startswith('/assets/'))
