"""шаг 23: crawl rules and discovery of the existing sitemap index."""
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_safe


@require_safe
def robots_txt(request):
    # These are crawl rules only; existing authorization stays in the views.
    excluded = (
        '/admin/', '/account/', '/catalog/manage/', '/search/', '/wishlist/',
        '/catalog/comparison/', '/catalog/recently-viewed/',
    )
    lines = ['User-agent: *']
    lines.extend(f'Disallow: {path}' for path in excluded)
    lines.extend(['', 'Sitemap: ' + request.build_absolute_uri(reverse('sitemap')), ''])
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
