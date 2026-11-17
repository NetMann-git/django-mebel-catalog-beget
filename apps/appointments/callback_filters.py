"""Read-only filtering and safe return parameters for the manager inbox."""
import re
from urllib.parse import urlencode
from django.db.models import F, Q, Value
from django.db.models.functions import Replace
from .models import CallbackRequest

QUERY_LIMIT = 200
PAGE_SIZE = 20


def clean_query(value):
    return str(value or '').strip()[:QUERY_LIMIT]


def search_callbacks(queryset, query):
    if not query:
        return queryset
    if re.fullmatch(r'#[0-9]+', query):
        number = query[1:].lstrip('0')
        if not number or len(number) > 19 or int(number) > 9223372036854775807:
            return queryset.none()
        return queryset.filter(pk=int(number))
    # A literal, escaped pattern gives Unicode-insensitive matching on SQLite too.
    pattern = re.escape(query)
    match = Q()
    for field in ('name', 'phone', 'email', 'city', 'comment', 'product__title'):
        match |= Q(**{field + '__iregex': pattern})
    if re.fullmatch(r'[+0-9\s().-]+', query):
        digits = re.sub(r'[^0-9]', '', query)
        if len(digits) >= 4:
            normalized = F('phone')
            for character in (' ', '+', '-', '(', ')', '.', '\u00a0', '\u202f', '\t'):
                normalized = Replace(normalized, Value(character), Value(''))
            queryset = queryset.annotate(search_phone=normalized)
            match |= Q(search_phone__contains=digits)
    return queryset.filter(match)


def due_follow_ups(today):
    return Q(status=CallbackRequest.STATUS_NEW, follow_up_on__lte=today)


def filter_query(status, query, page=None, *, due=False):
    params = {'due': '1'} if due else {}
    if status:
        params['status'] = status
    if query:
        params['q'] = clean_query(query)
    if page is not None:
        try:
            number = int(page)
        except (ValueError, TypeError):
            number = 1
        if 1 < number <= 1000000:
            params['page'] = number
    return urlencode(params)
