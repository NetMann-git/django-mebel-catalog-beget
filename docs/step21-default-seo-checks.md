# Шаг 21 — мебельные SEO-тексты по умолчанию

Основа: dev_gpt 256b331, после шага 20.
В config/templates/base.html заменены четыре автомобильных значения:
заголовок, description, og:title, og:description. Используются LUSTRID.RU
и описание мебели и столярных изделий на заказ для дома и бизнеса.
Пользовательские page.seo_title, page.title, page.search_description
и суффикс site.site_name сохранены. Дочерние SEO-блоки не изменены.
URL, robots, верстка, права доступа, галерея, «Тип изделия» и данные
не изменялись. Старые автомобильные страницы и инструменты не удалялись.

## Автоматически
44 теста прошли на отдельной тестовой SQLite, config.settings.dev:
apps.products.tests.test_furniture_default_seo,
apps.products.tests.test_furniture_viewport,
apps.products.tests.test_furniture_brand_page,
apps.products.tests.test_furniture_catalog,
apps.products.tests.test_furniture_detail, apps.recommendations, apps.wishlist.
Новые проверки: мебельные значения без page; сохранение индивидуальных
SEO-полей и site_name; HTML-экранирование кавычек и амперсанда;
сохранение page.title при пустом seo_title.
Django system check: 0 ошибок. git diff --check: успешно.
Установщик на отдельной копии: check без записи, apply/rollback,
конфликты старого и нового файлов до записи, CRLF/LF с точным откатом,
отказ отката после ручных правок, установка и откат распакованного ZIP.

## Браузер и ручная проверка
В этом шаге браузер не запускался: меняются только тексты метаданных,
их фактический HTML проверен автоматически. После установки посмотреть
исходный код страницы входа: description и og:title должны быть мебельными.
Проверить, что индивидуальные SEO-поля изделия и бренда сохранены.
Windows, MySQL/Beget и production непосредственно не проверялись.
Миграции и резервная копия БД не нужны, база патчем не изменяется.
