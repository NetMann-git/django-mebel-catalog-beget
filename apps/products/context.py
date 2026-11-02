# apps/products/context.py
"""
Контекст-билдеры для страниц товаров и каталога.
"""

from apps.products.querysets import CatalogQuerySet
from apps.products.filters import CatalogFilter
from apps.products.pagination import CatalogPaginator

from apps.products.repository import CatalogRepository


class CatalogContextBuilder:
    @staticmethod
    def build(request):
        # 1. Базовый запрос
        products = CatalogRepository.catalog()

        # 2. Фильтры
        filters = CatalogFilter(request.GET)
        products = filters.apply(products)

        # 3. Пагинация
        pagination = CatalogPaginator(products, request)

        # 4. Сборка контекста
        context = CatalogRepository.filters()
        context.update(filters.context())
        context.update(pagination.context())

        # Списки ограничены значениями опубликованных автомобилей.
        from apps.products.models import AttributeValue, ProductAttribute, CarModel
        from apps.products.filters import FUEL_SLUGS, parse_number

        active_attributes = ProductAttribute.objects.filter(
            product__is_active=True,
        )
        years = AttributeValue.objects.filter(
            product_attributes__in=active_attributes.filter(
                attribute_type__slug="year",
            ),
        ).values_list("value", flat=True).distinct()
        context["catalog_years"] = sorted(
            {int(number) for value in years
             if (number := parse_number(value)) is not None
             and number == int(number)},
            reverse=True,
        )
        context["fuel_values"] = AttributeValue.objects.filter(
            product_attributes__in=active_attributes.filter(
                attribute_type__slug__in=FUEL_SLUGS,
            ),
        ).distinct().order_by("value")

        context["catalog_models"] = CarModel.objects.select_related("brand").all()
        context["active_filter_count"] = sum(bool(value) for value in (
            filters.brand, filters.model, filters.year, filters.query, filters.fuel_type,
            filters.price_min or filters.price_max, filters.mileage_min or filters.mileage_max,
            filters.engine_volume_min or filters.engine_volume_max,
            filters.power_min or filters.power_max,
        ))
        context["advanced_filters_open"] = any((
            filters.query, filters.fuel_type, filters.engine_volume_min,
            filters.engine_volume_max, filters.power_min, filters.power_max,
        ))
        context["preserved_filters"] = [
            (key, request.GET[key]) for key in (
                "category", "availability", "transmission", "drive", "condition",
                "year_min", "year_max",
            ) if request.GET.get(key)
        ]

        # Шаг 05: контекст мебельной вёрстки, прежние GET-фильтры сохраняются.
        from apps.products.models import Category
        category_id = filters.category
        context["furniture_category_title"] = (
            Category.objects.filter(pk=category_id).values_list("title", flat=True).first()
            if category_id.isascii() and category_id.isdigit() and len(category_id) < 19 else None
        )
        legacy_keys = (
            "brand", "model", "year", "year_min", "year_max", "fuel_type", "availability",
            "transmission", "drive", "condition", "mileage_min", "mileage_max",
            "engine_volume_min", "engine_volume_max", "power_min", "power_max",
        )
        context["furniture_extra_filters"] = [
            (key, request.GET[key]) for key in legacy_keys if request.GET.get(key)
        ]
        context["furniture_sort_filters"] = [
            (key, value) for key, value in request.GET.items() if key not in ("sort", "page") and value
        ]
        context["furniture_has_filters"] = any((
            filters.query, filters.category, filters.price_min, filters.price_max,
            context["furniture_extra_filters"],
        ))

        # 5. Избранное (wishlist)
        if request.user.is_authenticated:
            wishlist_ids = list(request.user.favorites.values_list("product_id", flat=True))
        else:
            wishlist_ids = request.session.get('wishlist', [])
        context["wishlist_ids"] = wishlist_ids

        return context


class ProductContextBuilder:
    @staticmethod
    def build(product_page, request):
        from apps.products.services import ProductService
        context = ProductService.context(product_page)  # содержит similar_products

        # Избранное (wishlist)
        if request.user.is_authenticated:
            wishlist_ids = list(request.user.favorites.values_list("product_id", flat=True))
        else:
            wishlist_ids = request.session.get('wishlist', [])
        context["wishlist_ids"] = wishlist_ids

        return context


class HomeContextBuilder:
    """
    Формирует контекст главной страницы.
    """

    @staticmethod
    def build(request):
        context = {
            "featured_products": CatalogRepository.featured(),
        }
        # Можно также добавить wishlist_ids для главной, если там есть кнопки избранного (пока не нужно)
        return context