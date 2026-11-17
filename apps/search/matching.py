"""Shared furniture matching for the catalog, results page and suggestions."""
import re

from django.db.models import Case, Exists, F, Func, OuterRef, Q, Value, When
from django.db.models.functions import Lower, Replace

from apps.products.models import Badge, EquipmentOption, ProductAttribute


class SearchText(Func):
    """Normalize Cyrillic consistently on SQLite and MySQL."""

    def __init__(self, field):
        super().__init__(F(field))

    def as_sqlite(self, compiler, connection, **extra_context):
        connection.ensure_connection()
        if getattr(connection, '_furniture_search_connection', None) is not connection.connection:
            connection.connection.create_function(
                'furniture_search_text', 1, normalize, deterministic=True,
            )
            connection._furniture_search_connection = connection.connection
        return super().as_sql(compiler, connection, function='furniture_search_text', **extra_context)

    def as_sql(self, compiler, connection, **extra_context):
        field = self.get_source_expressions()[0]
        expression = Replace(Lower(field), Value('ё'), Value('е'))
        return compiler.compile(expression)


def normalize(value):
    return value.lower().replace('ё', 'е') if value is not None else None


def query_words(query):
    return tuple(dict.fromkeys(re.findall(r'[^\W_]+', normalize(query))))


def text_fields(queryset, *fields):
    return queryset.alias(**{f'search_{index}': SearchText(field) for index, field in enumerate(fields)})


def contains_word(word, field_count):
    condition = Q()
    for index in range(field_count):
        condition |= Q(**{f'search_{index}__contains': word})
    return condition


def match_text(queryset, words, *fields):
    queryset = text_fields(queryset, *fields)
    for word in words:
        queryset = queryset.filter(contains_word(word, len(fields)))
    return queryset


def match_products(queryset, query):
    words = query_words(query)
    if not words or len(words) > 16:
        return queryset.none()
    fields = ('title', 'article', 'short_description', 'description', 'category__title', 'product_type')
    queryset = text_fields(queryset, *fields)
    attributes = ProductAttribute.objects.filter(product_id=OuterRef('pk'))
    equipment = EquipmentOption.objects.filter(products=OuterRef('pk'), is_active=True)
    badges = Badge.objects.filter(products=OuterRef('pk'))
    for word in words:
        queryset = queryset.filter(
            contains_word(word, len(fields))
            | Exists(match_text(attributes, (word,), 'attribute_type__name', 'attribute_value__value'))
            | Exists(match_text(equipment, (word,), 'name'))
            | Exists(match_text(badges, (word,), 'title'))
        )

    phrase = ' '.join(normalize(query).split())
    title_words = Q()
    for word in words:
        title_words &= Q(search_0__contains=word)
    relevance = Case(
        When(Q(search_1=phrase) | Q(search_0=phrase), then=Value(0)),
        When(search_0__startswith=phrase, then=Value(1)),
        When(title_words, then=Value(2)),
        default=Value(3),
    )
    return queryset.order_by(relevance, 'title', 'pk')
