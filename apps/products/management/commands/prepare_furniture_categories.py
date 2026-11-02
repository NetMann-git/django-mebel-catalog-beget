"""Шаг 03: дополнить справочник категориями мебели без удаления данных."""
import json
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError
from django.utils import timezone
from apps.products.cache_keys import CATALOG_FILTERS_KEY
from apps.products.database_backup import backup_database
from apps.products.furniture_categories import category_plan
from apps.products.models import Category


class Command(BaseCommand):
    help = "Шаг 03: проверить или добавить шесть мебельных категорий."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--check", action="store_true")
        mode.add_argument("--apply", action="store_true")
        parser.add_argument("--output", type=Path, help="Путь JSON-отчёта; по умолчанию patch-backups.")

    def handle(self, *args, **options):
        rows = list(Category.objects.values("pk", "title", "slug").order_by("pk"))
        plan = category_plan(rows)
        counts = {name: sum(item["action"] == action for item in plan)
                  for name, action in (("create", "create"), ("skip", "skip"), ("conflicts", "conflict"))}
        counts.update(update=0, delete=0)
        mode = "apply" if options["apply"] else "check"
        report = {"step": "03", "mode": mode, "status": "planned", "counts": counts,
                  "categories": plan, "created_ids": [], "database_backup": None}
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S-%f")
        output = options["output"] or Path(settings.BASE_DIR) / "patch-backups" / f"step03-categories-{mode}-{stamp}.json"
        output = output.resolve()
        db_name = str(settings.DATABASES["default"]["NAME"])
        if db_name != ":memory:" and output == Path(db_name).resolve():
            raise CommandError("Нельзя записывать отчёт поверх базы.")
        if output.exists():
            raise CommandError("Файл отчёта уже существует. Укажите новый путь.")
        output.parent.mkdir(parents=True, exist_ok=True)
        def save():
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        save()  # Проверяем возможность сохранения отчёта до любых записей в БД.
        self.stdout.write(json.dumps(counts, ensure_ascii=False))
        for item in plan:
            self.stdout.write(f"{item['action']}: {item['title']} ({item['slug']})")
        self.stdout.write(f"Отчёт: {output}")
        if counts["conflicts"]:
            report["status"] = "conflicts"
            save()
            raise CommandError("Найдены конфликты названий или URL. База не изменена.")
        if options["check"] or not counts["create"]:
            report["status"] = "checked" if options["check"] else "unchanged"
            save()
            self.stdout.write("База не изменена.")
            return
        try:
            backup = backup_database("step03-before-furniture-categories")
            report["database_backup"] = str(backup)
            report["status"] = "backup_verified"
            save()
            self.stdout.write(f"Проверенная копия БД: {backup}")
            with transaction.atomic():
                current = list(Category.objects.select_for_update().values("pk", "title", "slug").order_by("pk"))
                if category_plan(current) != plan:
                    raise CommandError("Справочник изменён после проверки. Повторите --check; изменений нет.")
                for item in plan:
                    if item["action"] == "create":
                        category = Category.objects.create(slug=item["slug"], title=item["title"])
                        report["created_ids"].append(category.pk)
                transaction.on_commit(lambda: cache.delete(CATALOG_FILTERS_KEY))
        except (CommandError, IntegrityError) as error:
            report["status"] = "aborted"
            report["created_ids"] = []
            save()
            if isinstance(error, CommandError):
                raise
            raise CommandError("Конфликт параллельной записи. Транзакция отменена.") from error
        report["status"] = "applied"
        save()
        self.stdout.write(self.style.SUCCESS(f"Создано категорий: {len(report['created_ids'])}. Существующие записи не изменены."))
