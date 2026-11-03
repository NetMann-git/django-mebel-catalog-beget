# apps/search/views.py

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.response import TemplateResponse
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.views.decorators.csrf import ensure_csrf_cookie
from apps.wishlist.services import wishlist_products

from .services import SearchService


def popular(request):
    """
    Возвращает топ-10 популярных запросов.
    """
    queries = SearchService.get_popular_queries(limit=10)
    return JsonResponse({'popular': queries})


@vary_on_headers('X-Requested-With')
def suggest(request):
    """
    AJAX-эндпоинт для автодополнения поиска.
    Возвращает JSON со списком товаров, категорий, бейджей.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []}, status=200)

    # Вызываем сервис
    results = SearchService.suggest(query, request)

    return JsonResponse({
        'query': query,
        'results': results,
    })


@ensure_csrf_cookie
def search(request):
    """
    Страница результатов поиска по товарам (без Wagtail).
    """
    search_query = request.GET.get("query", "").strip()
    page = request.GET.get("page", 1)

    # Поиск по товарам
    if search_query:
        service = SearchService()
        search_results = service.search(search_query).select_related('category', 'brand').prefetch_related('badges').order_by('title', 'pk')
    else:
        search_results = []

    # Пагинация
    paginator = Paginator(search_results, 10)
    try:
        search_results = paginator.page(page)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": search_results,
            "wishlist_ids": list(wishlist_products(request).values_list('pk', flat=True)),
        },
    )
