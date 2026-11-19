from django.core.management.base import BaseCommand
from apps.products.database_backup import backup_database


class Command(BaseCommand):
    help='Создать проверенную копию SQLite/MySQL в patch-backups перед миграцией текстов сайта.'
    requires_system_checks=[]

    def handle(self,*args,**options):
        self.stdout.write(self.style.SUCCESS(str(backup_database('step125-before-content'))))
