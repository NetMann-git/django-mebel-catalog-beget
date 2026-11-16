"""Manager-only gallery endpoints, sharing the existing product edit access."""
import json
import logging
import re

from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.users.constants import ROLE_ADMIN, ROLE_MANAGER
from apps.users.decorators import role_required
from .gallery_upload import add_photo, choose_cover, limits, lock_product, prepare_hashes
from .image_variants import image_variant
from .models import Product, ProductGalleryImage

logger = logging.getLogger(__name__)
SALT = 'products.gallery.selection.v1'


def editor(product_id: int) -> HttpResponse:
    """Return to the existing gallery editor."""
    return redirect(reverse('catalog:product_edit', args=[product_id]) + '#product-gallery')


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def prepare(request: HttpRequest, product_id: int) -> JsonResponse:
    """Validate a bounded selection or incrementally cache legacy hashes."""
    product = get_object_or_404(Product, pk=product_id)
    if request.POST.get('action') == 'snapshot':
        html = render_to_string('products/gallery/manager.html', {
            'product': product,
            'gallery_admin': request.resolver_match.url_name == 'products_product_gallery_prepare',
        }, request=request)
        return JsonResponse({'html': html})
    try:
        if request.POST.get('action') == 'hashes':
            return JsonResponse({'ready': prepare_hashes(product_id)})
        raw = request.POST.get('files', '')
        if len(raw) > 100000:
            raise ValueError
        files = json.loads(raw)
        cap = limits()
        if not isinstance(files, list) or not 1 <= len(files) <= cap['files']:
            raise ValidationError('Превышено допустимое количество файлов в подборке.')
        for item in files:
            if (not isinstance(item, dict) or type(item.get('size')) is not int
                    or not 0 < item['size'] <= cap['bytes']
                    or not isinstance(item.get('sha256'), str)
                    or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])):
                raise ValidationError('Недопустимый размер или контрольная сумма файла.')
        if sum(item['size'] for item in files) > cap['total']:
            raise ValidationError('Превышен общий размер выбранных файлов.')
        token = signing.dumps({
            'product': product_id, 'user': request.user.pk,
            'files': [{'size': f['size'], 'sha256': f['sha256']} for f in files],
        }, salt=SALT, compress=True)
        return JsonResponse({'token': token})
    except ValidationError as error:
        return JsonResponse({'error': ' '.join(error.messages)}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Не удалось прочитать список файлов.'}, status=400)
    except (OSError, DatabaseError):
        logger.exception('Ошибка подготовки галереи %s', product_id)
        return JsonResponse({'error': 'Не удалось проверить старые фотографии. Проверьте доступность файлов и повторите попытку.'}, status=409)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def upload(request: HttpRequest, product_id: int) -> JsonResponse:
    """Accept exactly one original covered by a signed selection manifest."""
    get_object_or_404(Product, pk=product_id)
    try:
        token = request.POST.get('token', '')
        if len(token) > 100000:
            raise signing.BadSignature
        batch = signing.loads(token, salt=SALT, max_age=7200)
        if batch['product'] != product_id or batch['user'] != request.user.pk:
            raise signing.BadSignature
        index = int(request.POST.get('index', '-1'))
        if index < 0 or index >= len(batch['files']):
            raise ValueError
        files = request.FILES.getlist('image')
        if len(files) != 1:
            raise ValidationError('Загружайте по одной фотографии за запрос.')
        status = add_photo(product_id, files[0], batch['files'][index])
        return JsonResponse({'status': status})
    except signing.BadSignature:
        return JsonResponse({'error': 'Срок очереди истёк. Нажмите «Загрузить» повторно.'}, status=400)
    except ValidationError as error:
        return JsonResponse({'error': ' '.join(error.messages)}, status=400)
    except (ValueError, KeyError, IndexError, TypeError):
        return JsonResponse({'error': 'Очередь повреждена. Выберите файлы заново.'}, status=400)
    except (OSError, DatabaseError):
        logger.exception('Ошибка загрузки фотографии автомобиля %s', product_id)
        return JsonResponse({'error': 'Не удалось сохранить файл. Повторите попытку; ранее загруженные фото сохранены.'}, status=409)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def cover(request: HttpRequest, image_id: int) -> HttpResponse:
    """Select an existing gallery image as the product cover."""
    photo = get_object_or_404(ProductGalleryImage, pk=image_id)
    with transaction.atomic():
        product = lock_product(photo.product_id)
        photo = get_object_or_404(product.gallery, pk=image_id)
        choose_cover(product, photo)
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'cover_url': image_variant(product.image, 'table')})
    messages.success(request, 'Обложка изменена.')
    return editor(product.pk)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def delete(request: HttpRequest, image_id: int) -> HttpResponse:
    """Delete through existing commit-aware file cleanup signals."""
    wants_json = request.headers.get('Accept') == 'application/json'
    photo = get_object_or_404(ProductGalleryImage, pk=image_id)
    with transaction.atomic():
        product = lock_product(photo.product_id)
        photo = get_object_or_404(product.gallery, pk=image_id)
        if product.image.name == photo.image.name:
            replacement = product.gallery.exclude(pk=photo.pk).exclude(image=photo.image.name).first()
            product.image = replacement.image.name if replacement else ''
            product.save(update_fields=['image'])
            Product.objects.filter(pk=product.pk).update(
                image_sha256=replacement.image_sha256 if replacement else '',
            )
        photo.delete()
        if wants_json:
            cover_ids = []
            if product.image:
                cover_ids = list(
                    product.gallery.filter(image=product.image.name).values_list('pk', flat=True)
                )
    if wants_json:
        return JsonResponse({
            'cover_url': image_variant(product.image, 'table') if product.image else '',
            'cover_ids': [str(pk) for pk in cover_ids],
        })
    messages.success(request, 'Фотография удалена. Если она была обложкой, выбрана следующая доступная.')
    return editor(product.pk)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def reorder(request: HttpRequest, product_id: int) -> HttpResponse:
    """Persist explicit positions without touching cover or publication status."""
    get_object_or_404(Product, pk=product_id)
    wants_json = request.headers.get('Accept') == 'application/json'
    try:
        with transaction.atomic():
            product = lock_product(product_id)
            photos = list(product.gallery.all())
            submitted = {key[6:] for key in request.POST if key.startswith('order_')}
            if submitted != {str(photo.pk) for photo in photos}:
                raise ValueError
            for photo in photos:
                value = request.POST[f'order_{photo.pk}']
                if not value.isdecimal() or not 0 <= int(value) <= 1000000:
                    raise ValueError
                photo.sort_order = int(value)
            ProductGalleryImage.objects.bulk_update(photos, ['sort_order'])
    except (ValueError, KeyError):
        error = 'Укажите целый порядок от 0 до 1000000 для каждого фото. Если галерея изменилась, обновите страницу.'
        if wants_json:
            return JsonResponse({'error': error}, status=400)
        messages.error(request, error)
    else:
        if wants_json:
            ordered = sorted(photos, key=lambda photo: (photo.sort_order, photo.pk))
            return JsonResponse({'order': [f'order_{photo.pk}' for photo in ordered]})
        messages.success(request, 'Порядок фотографий сохранён.')
    return editor(product_id)
