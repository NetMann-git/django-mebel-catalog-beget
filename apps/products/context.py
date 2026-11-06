# apps/products/context.py
"""
Контекст-билдеры для страниц товаров и каталога.
"""

from apps.products.filters import CatalogFilter, catalog_query_parameters, valid_id
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

        # Furniture-only context: no years, engines, fuel or car-model queries.
        from apps.products.models import Category
        params = catalog_query_parameters(request.GET)
        context["furniture_category_title"] = (
            Category.objects.filter(pk=filters.category).values_list("title", flat=True).first()
            if valid_id(filters.category) else None
        )
        context["furniture_extra_filters"] = [
            (key, params[key]) for key in ("brand", "availability") if params.get(key)
        ]
        context["furniture_sort_filters"] = [(key, value) for key, value in params.items() if key != "sort"]
        context["furniture_has_filters"] = any((
            filters.query, filters.category, filters.brand, filters.availability,
            filters.price_min, filters.price_max,
        ))
        context["active_filter_count"] = sum(bool(value) for value in (
            filters.query, filters.category, filters.brand, filters.availability,
            filters.price_min or filters.price_max,
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