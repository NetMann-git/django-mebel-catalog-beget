from django.core.management.base import BaseCommand
from apps.products.database_backup import backup_database


class Command(BaseCommand):
    help = "Создать проверенную копию базы в patch-backups перед миграцией шага 127."
    requires_system_checks = []

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(str(backup_database("step127-before-launch"))))
