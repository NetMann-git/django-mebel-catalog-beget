import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, ImageChops

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.products.management.commands.load_furniture_examples import catalog_data
from apps.products.management.commands.load_southern_examples import Command
from apps.products.models import Product, ProductGalleryImage


class SouthernExamplesTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.media = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def load(self, mode):
        call_command('load_southern_examples', mode, stdout=StringIO())

    def test_full_galleries_preserve_existing_items_and_manual_edits(self):
        rows = catalog_data(Command.data_dir, 8)
        self.assertEqual(len(rows), 20)
        self.assertNotIn('ikea', str(rows).lower())
        for row in rows:
            self.assertEqual(len({p['sha256'] for p in row['photos']}), 8)
            self.assertGreater(len(row['description']), 800)
            with Image.open(Command.data_dir / row['photos'][0]['file']) as cover:
                red, green, blue = cover.convert('RGB').split()
                self.assertGreater(ImageChops.difference(red, blue).getextrema()[1], 20)
        original = Product.objects.create(title='Прежний пример', article='EXAMPLE-118-01', slug='previous-example', price=100)
        self.load('--check')
        self.assertEqual(Product.objects.count(), 1)
        with patch('apps.products.management.commands.load_furniture_examples.backup_database', return_value='backup') as backup:
            self.load('--apply')
            backup.assert_called_once_with('step119-before-examples')
            self.assertEqual(Product.objects.count(), 21)
            self.assertEqual(ProductGalleryImage.objects.count(), 140)
            self.assertEqual(len(list(self.media.rglob('*.jpg'))), 160)
            for product in Product.objects.exclude(pk=original.pk):
                self.assertEqual(product.gallery.count(), 7)
                self.assertFalse(product.is_portfolio)
                with product.image.open('rb') as cover:
                    digest = hashlib.sha256(cover.read()).hexdigest()
                self.assertNotIn(digest, product.gallery.values_list('image_sha256', flat=True))
            item = Product.objects.exclude(pk=original.pk).first()
            response = self.client.get(item.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['furniture_photos']), 8)
            self.assertContains(response, 'По запросу')
            item.title = 'Моя редакция'
            item.save(update_fields=['title'])
            self.load('--apply')
            item.refresh_from_db()
            self.assertEqual(item.title, 'Моя редакция')
            self.assertEqual(backup.call_count, 1)
            original.refresh_from_db()
            self.assertEqual(original.price, 100)

    def test_failed_gallery_write_cleans_up(self):
        with patch('apps.products.management.commands.load_furniture_examples.backup_database', return_value='backup'):
            with patch('apps.products.management.commands.load_furniture_examples.ProductGalleryImage.objects.create', side_effect=OSError('failure')):
                with self.assertRaises(OSError):
                    self.load('--apply')
        self.assertFalse(Product.objects.exists())
        self.assertFalse(list(self.media.rglob('*.jpg')))
