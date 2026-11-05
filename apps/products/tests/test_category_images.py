from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from apps.home.furniture_showcase import category_images
from apps.products.category_management import CategoryForm
from apps.products.furniture_categories import FURNITURE_CATEGORIES
from apps.products.models import Category, Product


def photo(name='category.jpg', format='JPEG'):
    data = BytesIO()
    Image.new('RGB', (600, 400), '#b39772').save(data, format=format)
    return SimpleUploadedFile(name, data.getvalue(), content_type='image/jpeg')


class CategoryImageTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = self.settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.manager = get_user_model().objects.create_user('category-photo-manager')
        self.manager.profile.role = 'manager'
        self.manager.profile.save()
        self.client.force_login(self.manager)
        self.category = Category.objects.create(title='Шкафы', slug='shkafy')
        self.url = reverse('catalog:category_edit', args=[self.category.pk])

    def test_upload_original_preview_and_home_priority_over_product(self):
        Product.objects.create(title='Шкаф', slug='wardrobe', price=100, category=self.category, image='products/random.jpg')
        upload = photo()
        original = upload.read()
        upload.seek(0)
        response = self.client.post(self.url, {'title': 'Шкафы', 'slug': 'shkafy', 'image': upload})
        self.assertRedirects(response, reverse('catalog:category_list_manage'))
        self.category.refresh_from_db()
        self.assertTrue(self.category.image.name.startswith('categories/'))
        with self.category.image.open('rb') as saved:
            self.assertEqual(saved.read(), original)
        response = self.client.get(reverse('home'))
        soup = BeautifulSoup(response.content, 'html.parser')
        image = soup.select_one('#categories .fm-category img')
        self.assertEqual(image['src'], self.category.image.url)
        self.assertNotIn('/products/random.jpg', str(soup.select_one('#categories')))
        for url in [self.url, reverse('catalog:category_list_manage')]:
            self.assertContains(self.client.get(url), self.category.image.url)
        self.assertContains(self.client.get(self.url), 'enctype="multipart/form-data"')

    def test_keep_replace_and_clear_with_default_return(self):
        self.client.post(self.url, {'title': 'Шкафы', 'slug': 'shkafy', 'image': photo()})
        self.category.refresh_from_db()
        first = self.category.image.name
        self.client.post(self.url, {'title': 'Шкафы', 'slug': 'shkafy'})
        self.category.refresh_from_db()
        self.assertEqual(self.category.image.name, first)
        self.client.post(self.url, {'title': 'Шкафы', 'slug': 'shkafy', 'image': photo()})
        self.category.refresh_from_db()
        self.assertNotEqual(self.category.image.name, first)
        self.assertTrue((Path(self.media.name) / first).exists())
        self.client.post(self.url, {'title': 'Шкафы', 'slug': 'shkafy', 'image-clear': 'on'})
        self.category.refresh_from_db()
        self.assertFalse(self.category.image)
        self.assertEqual(self.category.display_image_url, '/static/home/images/categories/shkafy.webp')

    def test_invalid_oversize_or_unsupported_upload_does_not_save(self):
        uploads = [SimpleUploadedFile('bad.jpg', b'not an image'), photo('bad.svg'), photo('bad.png', 'GIF')]
        big = photo()
        big.size = 8 * 1024 * 1024 + 1
        uploads.append(big)
        for upload in uploads:
            with self.subTest(name=upload.name, size=upload.size):
                form = CategoryForm({'title': 'Шкафы', 'slug': 'shkafy'}, {'image': upload}, instance=self.category)
                self.assertFalse(form.is_valid())
                self.assertIn('image', form.errors)
        self.category.refresh_from_db()
        self.assertFalse(self.category.image)
        self.assertEqual(list(Path(self.media.name).rglob('*')), [])

    def test_authorization_csrf_and_create_upload(self):
        customer = get_user_model().objects.create_user('photo-customer')
        for user in [None, customer]:
            client = Client()
            if user:
                client.force_login(user)
            self.assertEqual(client.post(self.url, {'title': 'Шкафы', 'slug': 'shkafy', 'image': photo()}).status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.manager)
        self.assertEqual(strict.post(self.url, {'title': 'Шкафы', 'slug': 'shkafy', 'image': photo()}).status_code, 403)
        response = self.client.post(reverse('catalog:category_create'), {'title': 'Комоды', 'image': photo()})
        self.assertEqual(response.status_code, 302)
        category = Category.objects.get(title='Комоды')
        self.assertTrue(category.image)
        self.assertEqual(category.display_image_url, category.image.url)

    def test_six_defaults_and_conflict_protection(self):
        for slug, title in FURNITURE_CATEGORIES:
            category, _ = Category.objects.get_or_create(slug=slug, defaults={'title': title})
            self.assertEqual(category.display_image_url, f'/static/home/images/categories/{slug}.webp')
        self.assertEqual(category_images({}), {})
        images = category_images({slug.replace('-', '_'): '/' for slug, _ in FURNITURE_CATEGORIES})
        self.assertEqual(len(images), 6)
        self.category.title = 'Другая категория'
        self.category.save()
        self.assertEqual(self.category.display_image_url, '')
        response = self.client.get(reverse('home'))
        self.assertNotIn('shkafy', response.context['furniture_category_images'])
