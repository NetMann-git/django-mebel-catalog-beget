# apps/products/repository.py

from django.core.cache import cache
from apps.products.querysets import CatalogQuerySet
from apps.products.models import Brand

from .cache_keys import (
    CACHE_TIMEOUT,
    CATALOG_QUERYSET_KEY,
    CATALOG_FILTERS_KEY,
)
from apps.products.constants import AVAILABILITY_CHOICES

class CatalogRepository:

    @staticmethod
    def catalog():
        cache_key = CATALOG_QUERYSET_KEY
        queryset = cache.get(cache_key)
        if queryset is None:
            queryset = CatalogQuerySet.catalog_queryset()
            cache.set(cache_key, queryset, CACHE_TIMEOUT)
        return queryset

    @staticmethod
    def filters():
        cache_key = CATALOG_FILTERS_KEY
        data = cache.get(cache_key)
        if data is None:
            from apps.products.models import Category

            data = {
                "brands": Brand.objects.order_by("name"),
                "categories": Category.objects.order_by("title"),
                "availabilities": AVAILABILITY_CHOICES,
            }
            cache.set(cache_key, data, CACHE_TIMEOUT)
        return data

    @staticmethod
    def distinct(field):
        return CatalogQuerySet.distinct_values(field)

    @staticmethod
    def related(product):
        return CatalogQuerySet.base_product_queryset(product)

    @staticmethod
    def featured(limit=8):
        return CatalogQuerySet.featured(limit)

    @staticmethod
    def by_brand(brand):
        """
        Возвращает активные товары указанного бренда.
        """
        return CatalogQuerySet._with_related(
            CatalogQuerySet._base_queryset().filter(brand=brand)
        )