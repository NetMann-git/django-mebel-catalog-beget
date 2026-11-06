"""Validated filters for the furniture catalog."""
from decimal import Decimal, InvalidOperation
from django.db import connection
from django.db.models.functions import Lower
from django.http import QueryDict
from apps.products.models import Brand

CATALOG_FILTER_KEYS = ('q', 'category', 'brand', 'availability', 'price_min', 'price_max', 'sort')
CATALOG_SORTS = ('price_asc', 'price_desc', 'title_asc', 'title_desc')


def catalog_query_parameters(query):
    """Only supported furniture parameters can propagate into links/forms."""
    result = QueryDict(mutable=True)
    for key in CATALOG_FILTER_KEYS:
        value = query.get(key, '').strip()
        if value and (key != 'sort' or value in CATALOG_SORTS):
            result[key] = value
    return result


def parse_number(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value).replace('\u00a0', '').replace(' ', '').replace(',', '.'))
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def valid_id(value):
    return value.isascii() and value.isdigit() and len(value) <= 19 and 0 < int(value) <= 9223372036854775807


class CatalogFilter:
    """Search, category, brand, availability, RUB price and furniture sorting."""

    def __init__(self, request_get):
        params = catalog_query_parameters(request_get)
        self.query = params.get('q', '')
        self.category = params.get('category', '')
        self.brand = params.get('brand', '')
        self.availability = params.get('availability', '')
        self.sort = params.get('sort', '')
        self.price_min = params.get('price_min', '')
        self.price_max = params.get('price_max', '')
        self.errors = []
        lower = parse_number(self.price_min) if self.price_min else None
        upper = parse_number(self.price_max) if self.price_max else None
        if ((self.price_min and lower is None) or (self.price_max and upper is None)
                or (lower is not None and upper is not None and lower > upper)):
            self.errors.append('Проверьте диапазон: цена.')
        self.ranges = {'price': (lower, upper)}

    def apply(self, queryset):
        if self.errors:
            return queryset.none()
        if self.category:
            queryset = queryset.filter(category_id=self.category) if valid_id(self.category) else queryset.none()
        if self.brand:
            queryset = queryset.filter(brand_id=self.brand) if valid_id(self.brand) else queryset.none()
        if self.availability:
            queryset = queryset.filter(availability_status=self.availability)
        lower, upper = self.ranges['price']
        if lower is not None or upper is not None:
            queryset = queryset.filter(currency='RUB')
            if lower is not None:
                queryset = queryset.filter(price__gte=lower)
            if upper is not None:
                queryset = queryset.filter(price__lte=upper)
        if self.query:
            if connection.vendor == 'sqlite' and not self.query.isascii():
                needle = self.query.casefold()
                matching_ids = [pk for pk, title in queryset.values_list('pk', 'title') if needle in title.casefold()]
                queryset = queryset.filter(pk__in=matching_ids)
            else:
                queryset = queryset.filter(title__icontains=self.query)
        ordering = {
            'price_asc': ('price', 'pk'), 'price_desc': ('-price', 'pk'),
            'title_asc': (Lower('title'), 'pk'), 'title_desc': (Lower('title').desc(), 'pk'),
        }
        return queryset.order_by(*ordering[self.sort]) if self.sort else queryset

    def context(self):
        return {
            'search_query': self.query, 'selected_category': self.category,
            'selected_brand': self.brand,
            'selected_brand_name': (Brand.objects.filter(pk=self.brand).values_list('name', flat=True).first()
                                    if valid_id(self.brand) else None),
            'selected_sort': self.sort, 'selected_availability': self.availability,
            'selected_price_min': self.price_min, 'selected_price_max': self.price_max,
            'filter_errors': self.errors,
        }
