"""Проверенные снимки SQLite и MySQL перед обслуживанием данных."""
import logging
from contextlib import closing
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connections
from django.utils import timezone


def backup_sqlite(source, folder, prefix):
    source = Path(source).resolve()
    if not source.is_file():
        raise CommandError("Файловая SQLite не найдена. Изменения отменены.")
    target = Path(folder) / (prefix + ".sqlite3")
    temporary = target.with_suffix(".sqlite3.partial")
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(temporary)) as copy:
                original.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise CommandError("Резервная SQLite не прошла integrity_check.")
        if temporary.stat().st_size == 0:
            raise CommandError("Резервная SQLite пуста.")
        temporary.replace(target)
    except (OSError, sqlite3.Error) as error:
        raise CommandError("Не удалось создать и проверить SQLite. Изменения отменены.") from error
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError as cleanup_error:
            # Сохраняем первичную ошибку, даже если файл занят внешним процессом.
            logging.getLogger(__name__).warning(
                "Не удалось удалить незавершённый снимок %s: %s", temporary, cleanup_error
            )
    return target


def backup_database(prefix):
    connection = connections["default"]
    config = connection.settings_dict
    folder = Path(settings.BASE_DIR) / "patch-backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S-%f")
    prefix = prefix + "-" + stamp
    if connection.vendor == "sqlite":
        return backup_sqlite(config["NAME"], folder, prefix)
    if connection.vendor != "mysql":
        raise CommandError("Автоматический снимок поддерживает только SQLite и MySQL.")
    executable = shutil.which("mysqldump") or shutil.which("mariadb-dump")
    if not executable:
        raise CommandError("Не найден mysqldump/mariadb-dump. MySQL не изменена.")
    # --single-transaction даёт согласованный снимок только транзакционных таблиц.
    with connection.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                       "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' "
                       "AND ENGINE <> 'InnoDB'")
        if cursor.fetchone():
            raise CommandError("Обнаружены таблицы не InnoDB. Требуется отдельный штатный бэкап; изменений нет.")
    target = folder / (prefix + ".sql")
    temporary = target.with_suffix(".sql.partial")
    command = [executable, "--single-transaction", "--quick", "--hex-blob", "--comments", "--dump-date",
               "--default-character-set=utf8mb4", "--host=" + (config.get("HOST") or "localhost"),
               "--port=" + str(config.get("PORT") or "3306"), "--user=" + config["USER"],
               "--databases", "--", config["NAME"]]
    environment = os.environ.copy()
    environment["MYSQL_PWD"] = config.get("PASSWORD") or ""
    try:
        with temporary.open("xb") as output:
            completed = subprocess.run(command, stdout=output, stderr=subprocess.PIPE, env=environment, check=False)
        if completed.returncode:
            raise CommandError("mysqldump завершился с ошибкой. MySQL не изменена; проверьте права доступа.")
        with temporary.open("rb") as source:
            source.seek(0, 2)
            size = source.tell()
            source.seek(max(0, size - 8192))
            tail = source.read()
        if size == 0 or b"-- Dump completed" not in tail:
            raise CommandError("SQL-снимок не содержит отметки завершения. MySQL не изменена.")
        temporary.replace(target)
    except OSError as error:
        raise CommandError("Не удалось записать SQL-снимок. MySQL не изменена.") from error
    finally:
        temporary.unlink(missing_ok=True)
    return target
