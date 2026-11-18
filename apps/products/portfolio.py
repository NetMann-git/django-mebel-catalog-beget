"""Portfolio visibility rules shared by public and manager pages."""
from django.db.models import Exists, OuterRef, Q

from .models import ProductGalleryImage


def with_portfolio_photo(queryset):
    gallery = ProductGalleryImage.objects.exclude(image='').filter(product_id=OuterRef('pk'))
    return queryset.annotate(has_portfolio_photo=(
        (Q(image__isnull=False) & ~Q(image='')) | Exists(gallery)
    ))


def visible_portfolio():
    return Q(is_active=True, is_portfolio=True, has_portfolio_photo=True)
