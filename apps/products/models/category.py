# Категории товаров.
# apps/products/models/category.py
from django.db import models
from django.core.validators import FileExtensionValidator
from ..category_images import category_image_upload_to, validate_category_image_size


class Category(models.Model):
    title = models.CharField(max_length=100, unique=True, verbose_name="Название")
    slug = models.SlugField(unique=True)

    image = models.ImageField(
        upload_to=category_image_upload_to, blank=True, verbose_name="Изображение категории",
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']), validate_category_image_size],
        help_text="JPG, PNG или WebP, до 8 МБ. Рекомендуется горизонтальное фото 1200 × 800. Исходник сохраняется без сжатия.",
    )

    @property
    def display_image_url(self):
        from ..category_images import category_image_url
        return category_image_url(self)

    class Meta:
        ordering = ["title"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.title
