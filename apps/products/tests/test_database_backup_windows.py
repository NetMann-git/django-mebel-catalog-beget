"""Регрессия шага 04: Windows запрещает операции с открытыми SQLite-файлами."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sqlite3
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from apps.products.database_backup import backup_sqlite


class TrackedConnection(sqlite3.Connection):
    closed = False

    def close(self):
        super().close()
        self.closed = True


class SQLiteHandleTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'source.sqlite3'
        with closing(sqlite3.connect(self.source)) as db:
            db.execute('CREATE TABLE sample (value TEXT)')
            db.execute("INSERT INTO sample VALUES ('данные')")
            db.commit()
        self.real_connect = sqlite3.connect
        self.handles = []

    def connect(self, *args, **kwargs):
        connection = self.real_connect(*args, factory=TrackedConnection, **kwargs)
        self.handles.append(connection)
        return connection

    def test_both_connections_close_before_file_rename(self):
        replace = Path.replace
        def windows_replace(path, target):
            self.assertEqual(len(self.handles), 2)
            self.assertTrue(all(db.closed for db in self.handles), 'SQLite handles still open at rename')
            return replace(path, target)
        with patch('apps.products.database_backup.sqlite3.connect', side_effect=self.connect):
            with patch.object(Path, 'replace', windows_replace):
                backup = backup_sqlite(self.source, self.folder, 'step04-closed')
        self.assertTrue(backup.is_file())
        with closing(self.real_connect(backup)) as db:
            self.assertEqual(db.execute('SELECT value FROM sample').fetchone(), ('данные',))

    def test_source_closes_if_destination_connection_fails(self):
        def fail_destination(path, **kwargs):
            if str(path).endswith('.partial'):
                raise sqlite3.OperationalError('destination unavailable')
            return self.connect(path, **kwargs)
        with patch('apps.products.database_backup.sqlite3.connect', side_effect=fail_destination):
            with self.assertRaises(CommandError):
                backup_sqlite(self.source, self.folder, 'step04-open-failed')
        self.assertEqual(len(self.handles), 1)
        self.assertTrue(self.handles[0].closed)

    def test_handles_close_before_cleanup_after_copy_failure(self):
        unlink = Path.unlink
        def windows_unlink(path, *args, **kwargs):
            if str(path).endswith('.partial'):
                self.assertTrue(all(db.closed for db in self.handles))
            return unlink(path, *args, **kwargs)
        with patch('apps.products.database_backup.sqlite3.connect', side_effect=self.connect):
            with patch.object(TrackedConnection, 'backup', side_effect=sqlite3.OperationalError('copy failed')):
                with patch.object(Path, 'unlink', windows_unlink):
                    with self.assertRaises(CommandError):
                        backup_sqlite(self.source, self.folder, 'step04-copy-failed')
        self.assertEqual(len(self.handles), 2)
        self.assertTrue(all(db.closed for db in self.handles))
        self.assertFalse(list(self.folder.glob('*.partial')))

    def test_cleanup_failure_does_not_hide_primary_error(self):
        unlink = Path.unlink
        def locked_partial(path, *args, **kwargs):
            if str(path).endswith('.partial'):
                raise PermissionError('cleanup locked')
            return unlink(path, *args, **kwargs)
        with patch.object(Path, 'replace', side_effect=PermissionError('rename locked')):
            with patch.object(Path, 'unlink', locked_partial):
                with self.assertLogs('apps.products.database_backup', level='WARNING') as logs:
                    with self.assertRaises(CommandError) as error:
                        backup_sqlite(self.source, self.folder, 'step04-lock')
        self.assertIsInstance(error.exception.__cause__, PermissionError)
        self.assertEqual(str(error.exception.__cause__), 'rename locked')
        self.assertIn('cleanup locked', logs.output[0])
