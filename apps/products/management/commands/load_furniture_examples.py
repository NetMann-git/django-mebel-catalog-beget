"""Load the reference catalog while preserving existing and edited records."""
import hashlib
import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image

from apps.products.cache import CatalogCache
from apps.products.database_backup import backup_database
from apps.products.furniture_categories import category_plan
from apps.products.models import AttributeType, AttributeValue, Badge, Category, Product, ProductAttribute, ProductGalleryImage

DATA = Path(__file__).resolve().parents[2] / 'data' / 'furniture_examples'


def catalog_data():
    rows = json.loads((DATA / 'catalog.json').read_text(encoding='utf-8'))
    if len(rows) != 20 or len({row['slug'] for row in rows}) != 20:
        raise CommandError('Ожидаются 20 разных примеров.')
    for row in rows:
        if len(row['photos']) != 2:
            raise CommandError('У каждого примера должны быть две фотографии.')
        for photo in row['photos']:
            path = (DATA / photo['file']).resolve()
            if not path.is_relative_to((DATA / 'images').resolve()):
                raise CommandError('Недопустимый путь к фотографии.')
            if hashlib.sha256(path.read_bytes()).hexdigest() != photo['sha256']:
                raise CommandError('Фотография повреждена: ' + photo['file'])
            with Image.open(path) as image:
                image.verify()
    return rows


def categories_plan():
    plan = category_plan(list(Category.objects.values('pk', 'title', 'slug')))
    if any(item['action'] == 'conflict' for item in plan):
        raise CommandError('Названия или URL категорий конфликтуют. Проверьте справочник категорий.')
    return plan


def new_examples(rows):
    pending = []
    for row in rows:
        matches = list(Product.objects.filter(slug=row['slug'])) + list(
            Product.objects.filter(article=row['article']).exclude(slug=row['slug'])
        )
        if not matches:
            pending.append(row)
        elif len(matches) != 1 or matches[0].slug != row['slug'] or matches[0].article != row['article']:
            raise CommandError('Занят URL или артикул примера: ' + row['article'])
    return pending


class Command(BaseCommand):
    help = 'Добавить 20 примеров реальной мебели с фото и источниками. Повторный запуск сохраняет ручные правки.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--check', action='store_true')
        mode.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        rows = catalog_data()
        categories_plan()
        pending = new_examples(rows)
        self.stdout.write(f'Добавить: {len(pending)}. Уже существуют: {20 - len(pending)}.')
        for row in pending:
            self.stdout.write(f"{row['article']} — {row['title']}")
        if options['check'] or not pending:
            return

        backup = backup_database('step118-before-examples')
        self.stdout.write(f'Резервная копия БД: {backup}')
        written_files = []
        try:
            with transaction.atomic():
                pending = new_examples(rows)
                plan = categories_plan()
                categories = {}
                for item in plan:
                    if item['action'] == 'create':
                        category = Category.objects.create(slug=item['slug'], title=item['title'])
                    else:
                        category = Category.objects.get(pk=item['existing'][0]['pk'])
                    categories[item['slug']] = category
                badge, _ = Badge.objects.get_or_create(
                    slug='example-for-discussion', defaults={'title': 'Пример для обсуждения'},
                )
                first_categories = set()
                for row in pending:
                    featured = row['category'] not in first_categories
                    first_categories.add(row['category'])
                    product = Product.objects.create(
                        title=row['title'], slug=row['slug'], article=row['article'],
                        category=categories[row['category']], product_type=row['product_type'],
                        price=0, currency='RUB', availability_status='under_order',
                        is_active=True, is_featured=featured, is_portfolio=False,
                        short_description=row['short_description'], description=row['description'],
                        price_details=row['price_details'],
                        meta_title=row['title'] + ' — пример для обсуждения | LUSTRID.RU',
                        meta_description=row['short_description'][:255],
                    )
                    product.badges.add(badge)
                    for order, (label, value) in enumerate(row['attributes'].items()):
                        kind = AttributeType.objects.filter(name=label).first()
                        if kind is None:
                            kind = AttributeType.objects.create(
                                name=label, slug=f'example118-field-{order}', data_type='string',
                            )
                        option, _ = AttributeValue.objects.get_or_create(attribute_type=kind, value=value)
                        ProductAttribute.objects.create(
                            product=product, attribute_type=kind, attribute_value=option, sort_order=order,
                        )
                    for index, photo in enumerate(row['photos']):
                        raw = (DATA / photo['file']).read_bytes()
                        name = f"products/examples118/{row['article']}-{index + 1}-{photo['sha256'][:12]}.jpg"
                        if default_storage.exists(name):
                            with default_storage.open(name, 'rb') as existing:
                                if hashlib.sha256(existing.read()).hexdigest() != photo['sha256']:
                                    raise CommandError('Конфликт файла фотографии: ' + name)
                        else:
                            name = default_storage.save(name, ContentFile(raw))
                            written_files.append(name)
                        if index == 0:
                            product.image = name
                            product.image_sha256 = photo['sha256']
                            product.save(update_fields=['image', 'image_sha256'])
                        else:
                            ProductGalleryImage.objects.create(
                                product=product, image=name, image_sha256=photo['sha256'],
                                alt=row['title'] + ' — фото производителя', sort_order=index,
                            )
                transaction.on_commit(CatalogCache.clear_catalog)
        except Exception:
            for name in written_files:
                default_storage.delete(name)
            raise
        self.stdout.write(self.style.SUCCESS(f'Добавлено примеров: {len(pending)}.'))
