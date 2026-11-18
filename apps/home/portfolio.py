"""Public completed projects shared by the home page and portfolio."""
from django.db.models import Prefetch

from apps.products.models import Product, ProductAttribute, ProductGalleryImage
from apps.products.portfolio import visible_portfolio, with_portfolio_photo


def portfolio_projects():
    photos = ProductGalleryImage.objects.exclude(image='').only('product_id', 'image')
    attributes = ProductAttribute.objects.filter(
        attribute_value__isnull=False,
    ).select_related('attribute_type', 'attribute_value')
    return with_portfolio_photo(Product.objects.all()).filter(
        visible_portfolio(),
    ).select_related('category').prefetch_related(
        Prefetch('gallery', queryset=photos, to_attr='portfolio_photos'),
        Prefetch('attributes', queryset=attributes, to_attr='portfolio_attributes'),
    ).order_by('-pk')
