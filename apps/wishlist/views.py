# apps\wishlist\views.py

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.views.generic import ListView
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator

from apps.products.models import Product
from apps.recommendations.services import RecommendationService
from .models import Favorite
from .services import wishlist_products


@method_decorator(ensure_csrf_cookie, name="dispatch")
class WishlistView(ListView):
    model = Favorite
    template_name = "wishlist/wishlist.html"
    context_object_name = "favorites"
    allow_empty = True

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Favorite.objects.filter(
                user=self.request.user, product__is_active=True,
            ).select_related("product")
        return Favorite.objects.none()  # для гостей пустой queryset, товары будем брать из сессии

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        products = list(wishlist_products(self.request).select_related(
            "category",
        ).prefetch_related("badges"))
        wishlist_ids = [product.pk for product in products]

        # Получаем рекомендации для страницы «Избранное»
        recommended_products = RecommendationService.get_similar_products(
            viewed_products=products,
            page='wishlist',
            limit=4
        )

        context["products"] = products
        context["wishlist_ids"] = wishlist_ids
        context["is_guest"] = not self.request.user.is_authenticated
        context["recommended_products"] = recommended_products

        return context


@require_POST
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)

    if request.user.is_authenticated:
        favorite, created = Favorite.objects.get_or_create(user=request.user, product=product)
        if not created:
            favorite.delete()
            is_favorite = False
        else:
            is_favorite = True
        count = wishlist_products(request).count()
    else:
        wishlist = request.session.get('wishlist', [])
        if product.id in wishlist:
            wishlist.remove(product.id)
            is_favorite = False
        else:
            wishlist.append(product.id)
            is_favorite = True
        request.session['wishlist'] = wishlist
        count = wishlist_products(request).count()

    return JsonResponse({
        "is_favorite": is_favorite,
        "count": count,
    })


@require_POST
def clear_wishlist_ajax(request):
    """
    AJAX-очистка избранного.
    """
    if request.user.is_authenticated:
        Favorite.objects.filter(user=request.user).delete()
    else:
        request.session['wishlist'] = []
        request.session.modified = True

    return JsonResponse({
        "success": True,
        "count": 0,
    })