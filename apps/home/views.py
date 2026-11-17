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


def about(request):
    return render(request, "home/about_workshop.html")


def contacts(request):
    return render(request, "home/contacts.html")


def portfolio(request):
    from django.core.paginator import Paginator
    from django.db.models import Exists, OuterRef, Prefetch, Q

    from apps.products.models import Product, ProductGalleryImage

    photos = ProductGalleryImage.objects.exclude(image='').only('product_id', 'image')
    projects = Product.objects.filter(is_active=True, is_portfolio=True).filter(
        (Q(image__isnull=False) & ~Q(image='')) | Exists(photos.filter(product_id=OuterRef('pk'))),
    )
    categories = list(projects.exclude(category=None).order_by(
        'category__title', 'category__slug',
    ).values_list('category__slug', 'category__title').distinct())
    selected = request.GET.get('category', '')
    if selected in {slug for slug, _ in categories}:
        projects = projects.filter(category__slug=selected)
    else:
        selected = ''
    projects = projects.select_related('category').prefetch_related(
        Prefetch('gallery', queryset=photos, to_attr='portfolio_photos'),
    ).order_by('-pk')
    page = Paginator(projects, 12).get_page(request.GET.get('page'))
    return render(request, 'home/portfolio.html', {
        'categories': categories, 'selected': selected, 'page_obj': page,
    })
