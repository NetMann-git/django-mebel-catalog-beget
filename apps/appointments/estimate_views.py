from urllib.parse import urlencode
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.products.filters import valid_id
from apps.products.models import Product
from .estimate_forms import DIRECTIONS, EstimateRequestForm
from .estimate_service import save_estimate
from .views import _notify_saved_inquiry


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def estimate_request(request):
    product = None
    product_id = request.GET.get('product', '')
    if product_id:
        if not valid_id(product_id):
            from django.http import Http404
            raise Http404
        product = get_object_or_404(Product, pk=product_id, is_active=True)
    purpose = request.GET.get('purpose', 'similar')
    if purpose not in ('similar', 'order', 'detail'):
        purpose = 'similar'
    direction = request.GET.get('direction', '')
    if direction not in dict(DIRECTIONS):
        direction = product.category.slug if product and product.category and product.category.slug in dict(DIRECTIONS) else ''
    params = {'product': product.pk, 'purpose': purpose} if product else {}
    if direction:
        params['direction'] = direction
    form_url = reverse('furniture_request') + ('?' + urlencode(params) if params else '')
    form = EstimateRequestForm(request.POST, request.FILES) if request.method == 'POST' else EstimateRequestForm(initial={'direction': direction})
    if request.method == 'POST':
        if request.POST.get('website', '').strip():
            return redirect(form_url)
        if form.is_valid():
            source = {'similar':'similar_project', 'order':'product_order', 'detail':'product_detail'}[purpose] if product else 'site_callback'
            inquiry = save_estimate(form, product=product, source=source, notify=_notify_saved_inquiry)
            request.session['estimate_success'] = inquiry.pk
            return redirect(form_url)
    return render(request, 'appointments/estimate_request.html', {
        'callback_product': product, 'estimate_form': form, 'estimate_product': product, 'estimate_form_url': form_url,
        'estimate_success': request.session.pop('estimate_success', None),
    }, status=400 if request.method == 'POST' else 200)
