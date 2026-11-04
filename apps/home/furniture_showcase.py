"""Images for the six existing home categories, without editing catalog data."""
from django.db.models import OuterRef, Subquery
from apps.products.models import Category, Product
from apps.products.furniture_categories import FURNITURE_CATEGORIES


def category_images(category_urls):
    photos = Product.objects.filter(is_active=True, category_id=OuterRef('pk')).exclude(
        image='').exclude(image__isnull=True).order_by('-is_featured', '-pk')
    categories = Category.objects.filter(slug__in=[slug for slug, _ in FURNITURE_CATEGORIES]).annotate(
        preview_image=Subquery(photos.values('image')[:1]))
    storage = Product._meta.get_field('image').storage
    return {category.slug.replace('-', '_'): storage.url(category.preview_image)
            for category in categories
            if category.preview_image and category.slug.replace('-', '_') in category_urls}
