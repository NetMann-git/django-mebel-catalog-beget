"""Public wishlist selection shared by the page and its counters."""
from apps.products.models import Product


def wishlist_products(request):
    """Keep saved references, but expose only currently published products."""
    products = Product.objects.filter(is_active=True)
    if request.user.is_authenticated:
        return products.filter(favorited_by__user=request.user).order_by(
            '-favorited_by__created_at', '-pk',
        )
    return products.filter(pk__in=request.session.get('wishlist', []))
