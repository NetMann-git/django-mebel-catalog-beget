"""Category artwork shared by the home page and category editors."""
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.templatetags.static import static


MAX_CATEGORY_IMAGE_SIZE = 8 * 1024 * 1024


def category_image_upload_to(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'categories/{uuid4().hex}.{extension}'


def validate_category_image_size(value):
    if value.size > MAX_CATEGORY_IMAGE_SIZE:
        raise ValidationError('Изображение должно быть не больше 8 МБ.')


def category_image_url(category):
    if category.image:
        return category.image.url
    from .furniture_categories import FURNITURE_CATEGORIES
    if (category.slug, category.title) in FURNITURE_CATEGORIES:
        return static(f'home/images/categories/{category.slug}.webp')
    return ''
