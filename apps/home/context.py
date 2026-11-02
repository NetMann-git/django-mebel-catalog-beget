"""Контекст главной страницы автомобильного каталога."""

from apps.products.models import Brand
from apps.products.furniture_categories import furniture_category_urls
from apps.appointments.forms import CallbackRequestForm
from apps.products.repository import CatalogRepository
from django.db.models import Count, Q

from apps.reviews.models import Review

from .models import ClientShowcase, ContactSettings, TeamMember


class HomeContextBuilder:
    """Собирает данные главной страницы из существующих приложений проекта."""

    @staticmethod
    def build(request):
        featured_products = CatalogRepository.featured(limit=8)

        featured_brands = (
            Brand.objects
            .filter(products__is_active=True)
            .annotate(catalog_count=Count("products", distinct=True))
            .order_by("-catalog_count", "sort_order", "name", "pk")[:24]
        )

        published_clients = ClientShowcase.objects.filter(is_published=True)
        clients = published_clients.filter(
            Q(image__isnull=False, image__gt="")
        ).order_by("sort_order", "id")
        video_clients = published_clients.exclude(rutube_url="").order_by("sort_order", "id")

        team_members = TeamMember.objects.filter(is_published=True).filter(
            Q(image__isnull=False, image__gt="")
        ).order_by("sort_order", "id")

        contact_settings = ContactSettings.objects.filter(pk=1, is_published=True).first()

        reviews = (
            Review.objects
            .filter(is_published=True)
            .select_related("product", "user")
            .prefetch_related("images")
            .order_by("-created_at")[:4]
        )

        if request.user.is_authenticated:
            wishlist_ids = list(
                request.user.favorites.values_list("product_id", flat=True)
            )
        else:
            wishlist_ids = request.session.get("wishlist", [])

        return {
            "featured_products": featured_products,
            "featured_brands": featured_brands,
            "reviews": reviews,
            "clients": clients,
            "video_clients": video_clients,
            "team_members": team_members,
            "contact_settings": contact_settings,
            "wishlist_ids": wishlist_ids,
            "callback_form": CallbackRequestForm(),
            "furniture_category_urls": furniture_category_urls(),
        }
