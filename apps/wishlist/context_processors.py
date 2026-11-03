# apps/wishlist/context_processors.py
from .services import wishlist_products


def wishlist_count(request):
    return {"wishlist_count": wishlist_products(request).count()}
