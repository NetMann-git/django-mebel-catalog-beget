"""Согласованная и проверенная копия SQLite перед изменениями."""
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from apps.products.database_backup import backup_database


class Command(BaseCommand):
    help = "Сохранить проверенную SQLite в patch-backups перед миграциями."
    requires_system_checks = []

    def handle(self, *args, **options):
        if connections["default"].vendor != "sqlite":
            raise CommandError("Команда предназначена только для SQLite.")
        target = backup_database("before-migration")
        self.stdout.write(self.style.SUCCESS(f"Резервная копия: {target}"))
