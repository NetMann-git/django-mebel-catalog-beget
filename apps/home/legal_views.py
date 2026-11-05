"""Public informational and legal pages."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe


@require_safe
def public_offer(request: HttpRequest) -> HttpResponse:
    """Show ordering information without publishing a contractual offer."""
    response = render(request, 'home/legal/public_offer.html', {
        'page': {
            'title': 'Условия заказа мебели',
            'seo_title': 'Условия заказа мебели — LUSTRID.RU',
            'search_description': 'Обсуждение проекта мебели, материалов, комплектации и изготовления.',
        },
    })
    response['X-Robots-Tag'] = 'noindex, follow'
    return response


def _privacy_document(request: HttpRequest, template: str, title: str) -> HttpResponse:
    """Render an explicitly marked draft without advertising it to search engines."""
    response = render(request, template, {
        'page': {'title': title, 'seo_title': title + ' — LUSTRID.RU',
                 'search_description': title + ' сайта lustrid.ru.'},
    })
    response['X-Robots-Tag'] = 'noindex, follow'
    return response


@require_safe
def privacy_policy(request: HttpRequest) -> HttpResponse:
    """Display the privacy policy draft."""
    return _privacy_document(request, 'home/legal/privacy.html', 'Политика конфиденциальности')


@require_safe
def personal_data_consent(request: HttpRequest) -> HttpResponse:
    """Display the separate consent draft; viewing does not record consent."""
    return _privacy_document(
        request, 'home/legal/consent.html', 'Согласие на обработку персональных данных',
    )
