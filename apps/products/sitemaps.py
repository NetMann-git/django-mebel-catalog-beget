"""шаг 22: public furniture URLs, using existing publication rules."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Brand, Product


class PublicSitemap(Sitemap):
    # Keep each response bounded; the index exposes any following pages.
    limit = 1000


class StaticSitemap(PublicSitemap):
    def items(self):
        return ['home', 'catalog:catalog', 'furniture_services', 'furniture_materials', 'furniture_reviews', 'furniture_about', 'furniture_contacts', 'furniture_portfolio']

    def location(self, item):
        return reverse(item)


class ProductSitemap(PublicSitemap):
    def items(self):
        return Product.objects.filter(is_active=True).only('id', 'slug').order_by('pk')


class BrandSitemap(PublicSitemap):
    def items(self):
        # Brand pages are public even when they contain no published products.
        return Brand.objects.only('id', 'slug').order_by('pk')


sitemaps = {'pages': StaticSitemap, 'products': ProductSitemap, 'brands': BrandSitemap}
