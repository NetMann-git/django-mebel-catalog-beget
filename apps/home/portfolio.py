"""Public completed projects shared by the home page and portfolio."""
from django.db.models import Exists, OuterRef, Prefetch, Q

from apps.products.models import Product, ProductAttribute, ProductGalleryImage


def portfolio_projects():
    photos = ProductGalleryImage.objects.exclude(image='').only('product_id', 'image')
    attributes = ProductAttribute.objects.filter(
        attribute_value__isnull=False,
    ).select_related('attribute_type', 'attribute_value')
    return Product.objects.filter(is_active=True, is_portfolio=True).filter(
        (Q(image__isnull=False) & ~Q(image='')) | Exists(photos.filter(product_id=OuterRef('pk'))),
    ).select_related('category').prefetch_related(
        Prefetch('gallery', queryset=photos, to_attr='portfolio_photos'),
        Prefetch('attributes', queryset=attributes, to_attr='portfolio_attributes'),
    ).order_by('-pk')
