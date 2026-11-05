"""Remove only verified collected copies of step 72 legacy media."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def matches_entry(data, entry):
    if hashlib.sha256(data).hexdigest() == entry['sha256']:
        return True
    # SVG is text: Git on Windows can convert LF to CRLF during checkout.
    return (entry['path'].endswith('.svg') and bool(entry.get('sha256_lf'))
            and hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest() == entry['sha256_lf'])


class Command(BaseCommand):
    help = 'Проверить/убрать старые автомобильные медиа из STATIC_ROOT с резервной копией.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--check', action='store_true')
        mode.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not settings.STATIC_ROOT:
            self.stdout.write('STATIC_ROOT не задан; собранных копий нет.')
            return
        root = Path(settings.STATIC_ROOT).resolve()
        project = Path(settings.BASE_DIR).resolve()
        protected = [project / 'media', project / 'apps', project / 'config', project / 'patch-backups', Path(settings.MEDIA_ROOT).resolve()]
        if project.is_relative_to(root) or any(root == p or root.is_relative_to(p) for p in protected):
            raise CommandError('STATIC_ROOT пересекается с исходниками, media или резервными копиями.')
        entries = json.loads((project / 'docs/step72-legacy-media.json').read_text(encoding='utf-8'))
        found = []
        errors = []
        for entry in entries:
            path = root / entry['path']
            if not path.resolve().is_relative_to(root) or path.is_symlink():
                errors.append(str(path) + ': недопустимая ссылка')
            elif path.exists():
                if not path.is_file() or not matches_entry(path.read_bytes(), entry):
                    errors.append(str(path) + ': содержимое отличается; удаление отменено')
                else:
                    found.append((entry, path))
        if errors:
            raise CommandError('\n'.join(errors))
        self.stdout.write(f'Найдено старых копий: {len(found)}')
        if options['check'] or not found:
            return
        backup = project / 'patch-backups' / ('step72-collected-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        # Back up every file before removing any of them.
        for entry, path in found:
            target = backup / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        for entry, path in found:
            if not matches_entry(path.read_bytes(), entry):
                raise CommandError('Файл изменился во время очистки: ' + str(path))
        for entry, path in found:
            path.unlink()
        (backup / 'report.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write('Копии сохранены: ' + str(backup))
