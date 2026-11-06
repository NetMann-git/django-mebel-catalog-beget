"""Ссылки удаления отдельных условий фильтра каталога."""

from django import template
from apps.products.filters import catalog_query_parameters

register = template.Library()


@register.simple_tag(takes_context=True)
def catalog_without(context, *keys):
    """Сохранить остальные GET-параметры и сбросить страницу пагинации."""
    query = catalog_query_parameters(context["request"].GET)
    for key in (*keys, "page"):
        query.pop(key, None)
    encoded = query.urlencode()
    return "?" + encoded if encoded else "?"
