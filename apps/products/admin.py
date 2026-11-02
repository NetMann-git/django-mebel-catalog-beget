from .models import VehicleImportSource
from .models import EquipmentGroup, EquipmentOption
from .car_model_forms import CarModelForm, ProductModelForm
from .models import CarModel
# apps/products/admin.py

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.urls import path, reverse
from functools import partial
from . import gallery_management
from django.utils.html import format_html
from easy_thumbnails.files import get_thumbnailer
from .product_attribute_forms import ProductAttributeForm
from .cache import CatalogCache
from .templatetags.price_format import price_format

from .models import (
    Product,
    ProductGalleryImage,
    ProductAttribute,
    Badge,
    Category,
)


from .models import AttributeType
from .models import AttributeValue

from .models import Brand

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("logo_tag", "name", "slug", "country", "sort_order")
    list_editable = ("sort_order",)
    ordering = ("sort_order", "name")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "country")
    fieldsets = (
        (None, {"fields": ("name", "slug", "logo", "description", "country", "sort_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )

    @admin.display(description="Логотип")
    def logo_tag(self, obj):
        if not obj.logo:
            return format_html('<span style="color:#aaa;">Нет</span>')

        thumbnail = get_thumbnailer(obj.logo).get_thumbnail({
            "size": (60, 40),
            "crop": False,
        })
        return format_html(
            '<img src="{}" style="width:60px;height:40px;object-fit:contain;" alt="" />',
            thumbnail.url,
        )


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1
    fields = ("value", "sort_order")
    ordering = ("sort_order",)

@admin.register(AttributeType)
class AttributeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "data_type")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AttributeValueInline]

    def get_inlines(self, request, obj=None):
        """Free-entry types do not require predefined options."""
        if obj and obj.data_type != 'choice':
            return []
        return super().get_inlines(request, obj)


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    form = ProductAttributeForm
    extra = 1
    fields = ("attribute_type", "attribute_value", "free_value", "sort_order")
    ordering = ("sort_order",)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductModelForm
    save_on_top = True
    change_form_template = 'admin/products/product/change_form.html'

    def can_manage_gallery(self, request, obj):
        return self.has_change_permission(request, obj) and request.user.has_perms([
            'products.add_productgalleryimage', 'products.change_productgalleryimage',
            'products.delete_productgalleryimage',
        ])

    def get_fieldsets(self, request, obj=None):
        # Cover is managed by the gallery, so saving an old form cannot reset it.
        return [(name, {**options, 'fields': tuple(
            field for field in options['fields'] if field != 'image'
        )}) for name, options in super().get_fieldsets(request, obj)]

    def get_urls(self):
        urls = []
        for action in ('prepare', 'upload', 'cover', 'delete', 'reorder'):
            urls.append(path(
                'gallery/<int:identifier>/' + action + '/',
                self.admin_site.admin_view(partial(self.gallery_action, action=action)),
                name='products_product_gallery_' + action,
            ))
        return urls + super().get_urls()

    def gallery_action(self, request, identifier, action):
        from django.shortcuts import get_object_or_404
        if action in ('cover', 'delete'):
            photo = get_object_or_404(ProductGalleryImage, pk=identifier)
            obj = photo.product
        else:
            obj = get_object_or_404(Product, pk=identifier)
        if not self.can_manage_gallery(request, obj):
            raise PermissionDenied
        # Admin authenticates and checks model permissions above. Reuse the
        # existing POST-only handler beneath the manager-role decorator.
        response = getattr(gallery_management, action).__wrapped__(request, identifier)
        if response.status_code == 302:
            response['Location'] = reverse('admin:products_product_change', args=[obj.pk]) + '#product-gallery'
        return response

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        obj = self.get_object(request, object_id) if object_id else None
        context = dict(extra_context or {})
        context['gallery_product'] = obj
        context['gallery_can_edit'] = obj is not None and self.can_manage_gallery(request, obj)
        return super().changeform_view(request, object_id, form_url, context)


    def save_related(self, request, form, formsets, change):
        """Invalidate cached attributes after all inline values are saved."""
        super().save_related(request, form, formsets, change)
        CatalogCache.clear_catalog()
    list_display = (
        "title",
        "article",
        "category",
        "formatted_price",
        "availability_status",
        "is_featured",
        "is_active",
        "image_tag",
    )
    @admin.display(description="Цена", ordering="price")
    def formatted_price(self, obj):
        """Display grouped prices while retaining numeric sorting."""
        return price_format(obj.price)

    list_filter = (
        "category",
        "brand",
        "availability_status",
        "is_featured",
        "is_active",
    )
    search_fields = (
        "title",
        "article",
        "short_description",
        "description",
    )
    prepopulated_fields = {}
    filter_horizontal = ("badges",)
    view_on_site = False

    fieldsets = (
        ('Комплектация', {'fields': ('equipment',)}),
        (
            "Основное",
            {
                "fields": (
                    "title",
                    "slug",
                    "regenerate_slug",
                    "article",
                    "category",
                    "brand",
                    "car_model",
                    "image",
                )
            },
        ),
        (
            "Описание",
            {
                "fields": (
                    "short_description",
                    "description",
                )
            },
        ),
        (
            "Каталог",
            {
                "fields": (
                    "price",
                    "currency",
                    "badges",
                )
            },
        ),
        (
            "SEO",
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                )
            },
        ),
        (
            "Публикация",
            {
                "fields": (
                    "is_featured",
                    "is_active",
                    "availability_status",
                )
            },
        ),
    )

    inlines = [
        ProductAttributeInline,
    ]

    def image_tag(self, obj):
        if obj.image:
            thumbnail = get_thumbnailer(obj.image).get_thumbnail({
                'size': (80, 60),
                'crop': True,
            })
            return format_html(
                '<img src="{}" style="width:80px; height:60px; object-fit: cover;" />',
                thumbnail.url
            )
        return format_html('<span style="color: #aaa;">Нет фото</span>')
    image_tag.short_description = "Фото"


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    """Manage the brand/model dictionary in Django admin."""

    form = CarModelForm
    list_display = ('name', 'brand', 'sort_order', 'slug')
    list_filter = ('brand',)
    search_fields = ('name', 'brand__name')
    list_select_related = ('brand',)

    def save_model(self, request, obj, form, change):
        """Refresh catalog caches after dictionary edits."""
        super().save_model(request, obj, form, change)
        CatalogCache.clear_catalog()

    def delete_model(self, request, obj):
        """Refresh catalog caches after dictionary deletion."""
        super().delete_model(request, obj)
        CatalogCache.clear_catalog()

    def delete_queryset(self, request, queryset):
        """Refresh caches after bulk deletion."""
        super().delete_queryset(request, queryset)
        CatalogCache.clear_catalog()


@admin.register(EquipmentGroup)
class EquipmentGroupAdmin(admin.ModelAdmin):
    """Edit equipment headings and their order."""

    list_display = ('name', 'slug', 'sort_order')
    list_editable = ('sort_order',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(EquipmentOption)
class EquipmentOptionAdmin(admin.ModelAdmin):
    """Maintain shared options without rewriting vehicle selections."""

    list_display = ('name', 'group', 'encar_standard_code', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    list_filter = ('group', 'is_active')
    search_fields = ('name', 'encar_standard_code')

    def has_delete_permission(self, request, obj=None):
        """Keep historical selections; disable options instead of deleting them."""
        return False


@admin.register(VehicleImportSource)
class VehicleImportSourceAdmin(admin.ModelAdmin):
    """Read-only diagnostics of confirmed imports."""

    list_display = ('listing_id', 'internal_vehicle_id', 'product', 'imported_at')
    search_fields = ('listing_id', 'internal_vehicle_id', 'product__title')
    readonly_fields = tuple(field.name for field in VehicleImportSource._meta.fields)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
