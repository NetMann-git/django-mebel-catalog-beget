# apps/search/services.py

from hashlib import sha256
from urllib.parse import urlencode

from django.core.cache import cache
from django.urls import reverse
from apps.products.image_variants import image_variant
from apps.products.models import Product, Category, Badge, ProductAttribute
from .matching import match_products, match_text, query_words
from .models import SearchQuery


class SearchService:
    LIMIT = 8

    @staticmethod
    def _thumbnail_url(image):
        return image_variant(image, 'thumb') if image else None

    @staticmethod
    def search(query):
        return match_products(Product.objects.filter(is_active=True), query)

    @staticmethod
    def suggest(query, request=None):
        words = query_words(query)
        if not words or len(words) > 16:
            return []

        matched_products = SearchService.search(query).select_related(
            'category', 'brand',
        ).prefetch_related('badges')[:SearchService.LIMIT]

        product_results = []
        for product in matched_products:
            product_results.append({
                'type': 'product',
                'id': product.id,
                'title': product.title,
                'price': str(product.price),
                'currency': product.currency,
                'url': product.get_absolute_url(),
                'image': SearchService._thumbnail_url(product.image),
                'badges': [{'title': b.title, 'slug': b.slug} for b in product.badges.all()],
                'category': product.category.title if product.category else None,
                'brand': product.brand.name if product.brand else None,
            })

        catalog_url = reverse('catalog:catalog')
        categories = match_text(Category.objects.order_by('title', 'pk'), words, 'title')
        category_results = [
            {'type': 'category', 'title': category.title,
             'url': catalog_url + '?' + urlencode({'category': category.pk})}
            for category in categories[:3]
        ]
        badges = match_text(Badge.objects.order_by('title', 'pk'), words, 'title')
        badge_results = [
            {'type': 'badge', 'title': badge.title,
             'url': catalog_url + '?' + urlencode({'q': badge.title})}
            for badge in badges[:3]
        ]

        attributes = ProductAttribute.objects.filter(
            product__is_active=True, attribute_value__isnull=False,
        ).select_related('product', 'attribute_type', 'attribute_value').order_by('sort_order', 'pk')
        matched_attrs = match_text(attributes, words, 'attribute_type__name', 'attribute_value__value')[:5]
        attribute_results = []
        for attr in matched_attrs:
            product = attr.product
            attribute_results.append({
                'type': 'attribute',
                'title': f"{attr.attribute_type.name}: {attr.attribute_value.value}",
                'product_title': product.title,
                'url': product.get_absolute_url(),
                'image': SearchService._thumbnail_url(product.image),
                'price': str(product.price),
                'currency': product.currency,
            })

        if request:
            query_key = sha256(query.lower().encode()).hexdigest()
            if cache.add(f'search_history:{query_key}', True, 300):
                SearchService.save_query(query, request)

        return (product_results + category_results + badge_results + attribute_results)[:10]

    @staticmethod
    def get_popular_queries(limit=10):
        from django.db.models import Sum

        return list(
            SearchQuery.objects
            .values('query')
            .annotate(total=Sum('count'))
            .order_by('-total')[:limit]
            .values_list('query', flat=True)
        )

    @staticmethod
    def save_query(query, request):
        if len(query) < 2:
            return
        if request.user.is_authenticated:
            obj, created = SearchQuery.objects.get_or_create(
                query=query,
                user=request.user,
                defaults={'count': 1}
            )
            if not created:
                obj.count += 1
                obj.save()
        else:
            history = request.session.get('search_history', [])
            if query in history:
                history.remove(query)
            history.insert(0, query)
            if len(history) > 10:
                history = history[:10]
            request.session['search_history'] = history
