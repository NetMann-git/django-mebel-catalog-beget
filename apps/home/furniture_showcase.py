"""The home page uses category artwork, independently of product photos."""
from apps.products.models import Category
from apps.products.furniture_categories import FURNITURE_CATEGORIES


def category_images(category_urls):
    categories = Category.objects.filter(slug__in=[slug for slug, _ in FURNITURE_CATEGORIES])
    return {category.slug.replace('-', '_'): category.display_image_url
            for category in categories
            if category.slug.replace('-', '_') in category_urls and category.display_image_url}
