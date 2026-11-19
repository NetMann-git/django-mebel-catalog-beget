from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.products.models import Product, ProductAttribute, ProductGalleryImage


class FurnitureExamplesTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.media = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def load(self, mode):
        call_command('load_furniture_examples', mode, stdout=StringIO())

    def test_check_apply_and_retry_preserve_existing_products_and_edits(self):
        existing = Product.objects.create(title='Моя работа', slug='own-work', price=50000)
        self.load('--check')
        self.assertEqual(Product.objects.count(), 1)
        self.assertFalse(list(self.media.rglob('*.jpg')))

        with patch('apps.products.management.commands.load_furniture_examples.backup_database', return_value='verified-backup') as backup:
            self.load('--apply')
            backup.assert_called_once_with('step118-before-examples')
            self.assertEqual(Product.objects.count(), 21)
            examples = Product.objects.filter(article__startswith='EXAMPLE-118-')
            self.assertEqual(examples.count(), 20)
            self.assertEqual(examples.values('category').distinct().count(), 6)
            self.assertEqual(ProductGalleryImage.objects.count(), 20)
            self.assertEqual(ProductAttribute.objects.count(), 100)
            self.assertFalse(examples.filter(is_portfolio=True).exists())
            self.assertEqual(len(list(self.media.rglob('*.jpg'))), 40)

            item = examples.first()
            item.description = 'Моё описание после редактирования'
            item.save(update_fields=['description'])
            self.load('--apply')
            item.refresh_from_db()
            existing.refresh_from_db()
            self.assertEqual(item.description, 'Моё описание после редактирования')
            self.assertEqual(existing.price, 50000)
            self.assertEqual(Product.objects.count(), 21)
            self.assertEqual(backup.call_count, 1)

            # A source link is clickable, pictures use variants and unknown price is clear.
            detail = examples.exclude(pk=item.pk).first()
            response = self.client.get(detail.get_absolute_url())
            self.assertContains(response, 'По запросу')
            self.assertContains(response, 'Пример для обсуждения')
            self.assertContains(response, 'href="https://www.ikea.com/')
            self.assertEqual(len(response.context['furniture_photos']), 2)
            catalog = self.client.get(reverse('catalog:catalog'))
            self.assertContains(catalog, 'По запросу')

    def test_partial_failure_rolls_back_database_and_new_images(self):
        with patch('apps.products.management.commands.load_furniture_examples.backup_database', return_value='verified-backup'):
            with patch('apps.products.management.commands.load_furniture_examples.ProductGalleryImage.objects.create', side_effect=OSError('write failed')):
                with self.assertRaises(OSError):
                    self.load('--apply')
        self.assertFalse(Product.objects.exists())
        self.assertFalse(list(self.media.rglob('*.jpg')))
