# apps/home/views.py

from django.shortcuts import render

from .context import HomeContextBuilder


def home(request):
    context = HomeContextBuilder.build(request)
    return render(request, "home/home.html", context)


def services(request):
    from .services_content import SERVICE_GROUPS
    return render(request, "home/services.html", {"service_groups": SERVICE_GROUPS})


def materials(request):
    return render(request, "home/materials.html")


def reviews(request):
    from django.core.paginator import Paginator
    from apps.reviews.models import Review

    published = (Review.objects.filter(is_published=True, product__is_active=True)
                 .select_related("product", "user", "reply")
                 .prefetch_related("images").order_by("-created_at", "-pk"))
    page = Paginator(published, 12).get_page(request.GET.get("page"))
    return render(request, "home/reviews.html", {"page_obj": page})
