# apps\recommendations\views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from apps.users.decorators import role_required
from apps.users.constants import ROLE_MANAGER, ROLE_ADMIN
from django.contrib import messages
from .models import PromotedProduct
from .forms import PromotedProductForm
from django.core.paginator import Paginator


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def manage_recommendations(request):
    promotions_list = PromotedProduct.objects.select_related('product').order_by('-priority', '-id')
    paginator = Paginator(promotions_list, 10)  # по 10 на страницу, как в manage_list
    page_number = request.GET.get('page')
    promotions = paginator.get_page(page_number)
    return render(request, 'recommendations/manage.html', {
        'promotions': promotions,
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def add_recommendation(request):
    if request.method == 'POST':
        form = PromotedProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Изделие добавлено в рекомендации.')
            return redirect('recommendations:manage')
    else:
        form = PromotedProductForm()
    return render(request, 'recommendations/add.html', {'form': form})


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def edit_recommendation(request, pk):
    promotion = get_object_or_404(PromotedProduct, pk=pk)
    if request.method == 'POST':
        form = PromotedProductForm(request.POST, instance=promotion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Изменения сохранены.')
            return redirect('recommendations:manage')
    else:
        form = PromotedProductForm(instance=promotion)
    return render(request, 'recommendations/edit.html', {'form': form, 'promotion': promotion})


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def delete_recommendation(request, pk):
    promotion = get_object_or_404(PromotedProduct, pk=pk)
    if request.method != 'POST':
        return render(request, 'recommendations/delete.html', {'promotion': promotion})
    promotion.delete()
    messages.success(request, 'Рекомендация удалена.')
    return redirect('recommendations:manage')


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def toggle_active(request, pk):
    promotion = get_object_or_404(PromotedProduct, pk=pk)
    promotion.is_active = not promotion.is_active
    promotion.save()
    messages.success(request, 'Рекомендация включена.' if promotion.is_active else 'Рекомендация выключена.')
    return redirect('recommendations:manage')