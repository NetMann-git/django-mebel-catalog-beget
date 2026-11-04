# config/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps import views as sitemap_views
from django.urls import include, path

from apps.home.views import home, services, materials, reviews
from apps.home.legal_views import public_offer, privacy_policy, personal_data_consent
from apps.products.sitemaps import sitemaps
from .seo_views import robots_txt

urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_views.index,
         {'sitemaps': sitemaps, 'sitemap_url_name': 'sitemap_section'}, name='sitemap'),
    path('sitemap-<section>.xml', sitemap_views.sitemap,
         {'sitemaps': sitemaps}, name='sitemap_section'),
    path('admin/', admin.site.urls),
    path('smart_selects/', include('smart_selects.urls')),  # ДОБАВИТЬ ЭТУ СТРОКУ
    path('', home, name='home'),
    path('services/', services, name='furniture_services'),
    path('materials/', materials, name='furniture_materials'),
    path('reviews/', reviews, name='furniture_reviews'),
    path('terms/', public_offer, name='public_offer'),
    path('privacy/', privacy_policy, name='privacy_policy'),
    path('consent/', personal_data_consent, name='personal_data_consent'),
    path('catalog/', include('apps.products.urls')),
    path('wishlist/', include('apps.wishlist.urls')),
    path('reviews/', include('apps.reviews.urls')),
    path('appointments/', include('apps.appointments.urls')),
    path('size-helper/', include('apps.size_helper.urls')),
    path('account/', include('apps.users.urls')),
    path('account/content/', include('apps.home.urls')),
    path('search/', include('apps.search.urls')),
    path('recommendations/', include('apps.recommendations.urls', namespace='recommendations')),
    path('calculator/', include('apps.calculator.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
