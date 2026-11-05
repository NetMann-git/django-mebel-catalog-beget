import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class LegacyCleanupTests(SimpleTestCase):
    def test_check_apply_backup_and_unrelated_file(self):
        with TemporaryDirectory() as directory:
            project = Path(directory)
            root = project / 'staticfiles'
            path = root / 'home/video/cars_video.mp4'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'old movie')
            other = root / 'furniture.webp'
            other.write_bytes(b'furniture')
            (project / 'docs').mkdir()
            entry = {'path': 'home/video/cars_video.mp4', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            (project / 'docs/step72-legacy-media.json').write_text(json.dumps([entry]))
            with override_settings(BASE_DIR=project, STATIC_ROOT=root):
                call_command('clean_legacy_static', check=True, stdout=StringIO())
                self.assertTrue(path.exists())
                call_command('clean_legacy_static', apply=True, stdout=StringIO())
                self.assertFalse(path.exists())
                self.assertEqual(other.read_bytes(), b'furniture')
                backup = next((project / 'patch-backups').glob('*/home/video/cars_video.mp4'))
                self.assertEqual(backup.read_bytes(), b'old movie')
                call_command('clean_legacy_static', apply=True, stdout=StringIO())

    def test_conflict_prevents_all_deletions(self):
        with TemporaryDirectory() as directory:
            project = Path(directory)
            root = project / 'staticfiles'
            root.mkdir()
            (project / 'docs').mkdir()
            entries = []
            for name in ['one.mp4', 'two.mp4']:
                (root / name).write_bytes(b'old')
                entries.append({'path': name, 'sha256': hashlib.sha256(b'old').hexdigest()})
            (project / 'docs/step72-legacy-media.json').write_text(json.dumps(entries))
            (root / 'two.mp4').write_bytes(b'custom')
            with override_settings(BASE_DIR=project, STATIC_ROOT=root):
                with self.assertRaises(CommandError):
                    call_command('clean_legacy_static', apply=True, stdout=StringIO())
            self.assertTrue((root / 'one.mp4').exists())
            self.assertFalse((project / 'patch-backups').exists())


    def test_svg_crlf_backup_preserves_original_bytes(self):
        with TemporaryDirectory() as directory:
            project = Path(directory)
            root = project / 'staticfiles'
            root.mkdir()
            (project / 'docs').mkdir()
            lf = b'<svg>\n<path/>\n</svg>\n'
            crlf = lf.replace(b'\n', b'\r\n')
            entry = {'path': 'line.svg', 'sha256': hashlib.sha256(lf).hexdigest(),
                     'sha256_lf': hashlib.sha256(lf).hexdigest()}
            (project / 'docs/step72-legacy-media.json').write_text(json.dumps([entry]))
            path = root / 'line.svg'
            path.write_bytes(crlf)
            with override_settings(BASE_DIR=project, STATIC_ROOT=root):
                call_command('clean_legacy_static', check=True, stdout=StringIO())
                self.assertEqual(path.read_bytes(), crlf)
                path.write_bytes(crlf + b'<!-- custom -->')
                with self.assertRaises(CommandError):
                    call_command('clean_legacy_static', apply=True, stdout=StringIO())
                path.write_bytes(crlf)
                call_command('clean_legacy_static', apply=True, stdout=StringIO())
            backup = next((project / 'patch-backups').glob('*/line.svg'))
            self.assertEqual(backup.read_bytes(), crlf)
            self.assertFalse(path.exists())
