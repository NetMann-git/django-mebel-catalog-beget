# Шаг 23 — robots.txt и ссылка на XML-карту

Основа: установленный шаг 22 (ad3ac13), поверх dev_gpt c4e60a4.
На момент проверки dev_gpt ещё содержала шаг 21. Продолжение сделано
поверх проверенной рабочей копии шага 22, без отката её изменений.

Добавлен /robots.txt, GET/HEAD, text/plain; charset=utf-8.
Общая группа User-agent: * задаёт Disallow для семи префиксов:
/admin/, /account/, /catalog/manage/, /search/, /wishlist/,
/catalog/comparison/, /catalog/recently-viewed/.
Sitemap содержит абсолютную ссылку на существующий /sitemap.xml шага 22.
Домен, схема и порт берутся из запроса, старый SITE_URL не используется.
Главная, каталог, изделия, бренды, статические файлы, оригиналы фото
и XML-карта не запрещаются правилами обхода.
Это правила обхода, не изменение авторизации или гарантия деиндексации.
Существующие права доступа и meta robots остаются прежними.
База не читается этим обработчиком и не изменяется.

## Автоматически
53 теста прошли на отдельной тестовой SQLite, config.settings.dev:
apps.products.tests.test_furniture_robots,
apps.products.tests.test_furniture_sitemap,
apps.products.tests.test_furniture_default_seo,
apps.products.tests.test_furniture_viewport,
apps.products.tests.test_furniture_brand_page,
apps.products.tests.test_furniture_catalog,
apps.products.tests.test_furniture_detail, apps.recommendations, apps.wishlist.
Правила проверены RobotFileParser: публичные страницы/статика/медиа
разрешены, служебные префиксы и вложенные адреса запрещены для обхода.
Проверены HTTP localhost с портом, HTTPS lustrid.ru, единственная ссылка
Sitemap, plain text без HTML, HEAD, отказ POST/PUT/PATCH/DELETE (405).
Новые тесты SimpleTestCase запрещают обращения к базе данных.
Django check: 0 ошибок; git diff --check: успешно.

## Установка и откат
Проверены check без записи, apply, точный rollback, конфликты старого
и нового файла до первой записи, CRLF/LF, отказ отката при ручной правке,
распаковка финального ZIP и его установка/откат.
На отдельной полной копии исходников: установка из ZIP, Django check
после установки и восстановление исходных файлов при откате.

## Ручная проверка и ограничения
Открыть http://127.0.0.1:8000/robots.txt: обычный текст с User-agent,
семью Disallow и Sitemap: http://127.0.0.1:8000/sitemap.xml.
Затем открыть карту и каталог по прежним адресам.
Браузер не запускался: HTML-интерфейс не меняется, HTTP-ответ проверен тестами.
Windows, MySQL/Beget и production непосредственно не проверялись.
Миграции, новые pip-зависимости и резервная копия БД не нужны.
Заменённые исходники сохраняются в patch-backups/step23-*/original.
Публикация и отправка поисковым системам не выполнялись.

Источник синтаксиса: https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec
