"""Шаг 03: предварительная проверка, конфликты, повторяемость и снимки."""
from contextlib import closing
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import json
import sqlite3
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase, SimpleTestCase
from apps.products.cache_keys import CATALOG_FILTERS_KEY
from apps.products.database_backup import backup_sqlite, backup_database
from apps.products.furniture_categories import furniture_category_urls
from apps.products.models import Category, Product
from apps.products.filters import CatalogFilter


class FurnitureCategoryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        override = self.settings(BASE_DIR=Path(self.temp.name))
        override.enable()
        self.addCleanup(override.disable)
        cache.clear()

    def run_command(self, mode, **kwargs):
        call_command('prepare_furniture_categories', mode, stdout=StringIO(), **kwargs)

    def test_check_only_reports(self):
        output = Path(self.temp.name) / 'check.json'
        with patch('apps.products.management.commands.prepare_furniture_categories.backup_database') as backup:
            self.run_command('--check', output=output)
        backup.assert_not_called()
        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(json.loads(output.read_text())['counts'],
                         {'create': 6, 'skip': 0, 'conflicts': 0, 'update': 0, 'delete': 0})

    def test_idempotent_apply_preserves_old_categories_and_invalidates_cache(self):
        old = Category.objects.create(title='Седаны', slug='sedany')
        cache.set(CATALOG_FILTERS_KEY, {'old': True})
        with patch('apps.products.management.commands.prepare_furniture_categories.backup_database', return_value=Path(self.temp.name) / 'verified.sqlite3') as backup:
            with self.captureOnCommitCallbacks(execute=True):
                self.run_command('--apply')
            self.run_command('--apply')
            self.assertEqual(backup.call_count, 1)
        self.assertEqual(Category.objects.count(), 7)
        old.refresh_from_db()
        self.assertEqual((old.title, old.slug), ('Седаны', 'sedany'))
        self.assertIsNone(cache.get(CATALOG_FILTERS_KEY))
        self.assertEqual(len(furniture_category_urls()), 6)

    def test_conflicts_never_overwrite_or_add_other_categories(self):
        for title, slug in [('Шкафы', 'manual'), ('Ручное название', 'shkafy'), ('шкафы ', 'another')]:
            Category.objects.all().delete()
            Category.objects.create(title=title, slug=slug)
            with patch('apps.products.management.commands.prepare_furniture_categories.backup_database') as backup:
                with self.assertRaises(CommandError):
                    self.run_command('--apply')
            backup.assert_not_called()
            self.assertEqual(Category.objects.count(), 1)
            self.assertEqual(furniture_category_urls(), {})

    def test_backup_failure_prevents_writes(self):
        with patch('apps.products.management.commands.prepare_furniture_categories.backup_database', side_effect=CommandError('backup failed')):
            with self.assertRaises(CommandError):
                self.run_command('--apply')
        self.assertEqual(Category.objects.count(), 0)

    def test_partial_write_rolls_back(self):
        create = Category.objects.create
        count = 0
        def fail_second(**kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise IntegrityError('simulated concurrency')
            return create(**kwargs)
        with patch('apps.products.management.commands.prepare_furniture_categories.backup_database', return_value=Path(self.temp.name) / 'copy.sqlite3'):
            with patch.object(Category.objects, 'create', side_effect=fail_second):
                with self.assertRaises(CommandError):
                    self.run_command('--apply')
        self.assertEqual(Category.objects.count(), 0)

    def test_home_links_to_matching_category_and_filter_works(self):
        response = self.client.get('/')
        self.assertContains(response, 'class="fm-category" href="#callback"', count=6)
        category = Category.objects.create(title='Шкафы', slug='shkafy')
        item = Product.objects.create(title='Шкаф по размеру', slug='wardrobe-test', price=1, category=category)
        Product.objects.create(title='Другая мебель', slug='other-test', price=1)
        self.assertContains(self.client.get('/'), f'class="fm-category" href="/catalog/?category={category.pk}"', count=1)
        result = CatalogFilter({'category': str(category.pk)}).apply(Product.objects.filter(is_active=True))
        self.assertEqual(list(result), [item])

    def test_existing_report_is_not_overwritten(self):
        output = Path(self.temp.name) / 'existing.json'
        output.write_text('manual')
        with self.assertRaises(CommandError):
            self.run_command('--apply', output=output)
        self.assertEqual(output.read_text(), 'manual')
        self.assertEqual(Category.objects.count(), 0)


class DatabaseBackupTests(SimpleTestCase):
    def test_wal_sqlite_snapshot_is_valid_and_restores_data(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / 'source.sqlite3'
            with closing(sqlite3.connect(source)) as original:
                original.execute('PRAGMA journal_mode=WAL')
                original.execute('CREATE TABLE example (value TEXT)')
                original.execute("INSERT INTO example VALUES ('сохранено')")
                original.commit()
                backup = backup_sqlite(source, folder, 'step03-test')
            with closing(sqlite3.connect(backup)) as copy:
                self.assertEqual(copy.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
                with closing(sqlite3.connect(Path(folder) / 'restored.sqlite3')) as restored:
                    copy.backup(restored)
                    self.assertEqual(restored.execute('SELECT value FROM example').fetchone(), ('сохранено',))

    def test_mysql_dump_keeps_password_out_of_arguments_and_checks_completion(self):
        connection = MagicMock()
        connection.vendor = 'mysql'
        connection.settings_dict = {'NAME': 'catalog', 'HOST': 'localhost', 'PORT': '3306', 'USER': 'testuser', 'PASSWORD': 'test-secret'}
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        def dump(args, **kwargs):
            self.assertNotIn('test-secret', ' '.join(args))
            self.assertEqual(kwargs['env']['MYSQL_PWD'], 'test-secret')
            kwargs['stdout'].write(b'-- MySQL dump\nCREATE TABLE t(id int);\n-- Dump completed on test\n')
            return SimpleNamespace(returncode=0)
        with TemporaryDirectory() as folder, self.settings(BASE_DIR=Path(folder)):
            with patch('apps.products.database_backup.connections', {'default': connection}), patch('apps.products.database_backup.shutil.which', return_value='mysqldump'):
                with patch('apps.products.database_backup.subprocess.run', side_effect=dump):
                    self.assertTrue(backup_database('step03-test').is_file())
                with patch('apps.products.database_backup.subprocess.run', return_value=SimpleNamespace(returncode=1)):
                    with self.assertRaises(CommandError):
                        backup_database('step03-failed')
                self.assertFalse(list(Path(folder).rglob('*.partial')))
