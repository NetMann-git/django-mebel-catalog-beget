"""Category editing for managers and administrators."""

from typing import Any

from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from apps.users.constants import ROLE_ADMIN, ROLE_MANAGER
from apps.users.decorators import role_required
from .cache import CatalogCache
from .manager_slugs import AutoSlugMixin
from .models import Category
from .furniture_categories import FURNITURE_CATEGORIES


def _is_home_category(category):
    """The current homepage resolves these exact title/code pairs."""
    return bool(category and (category.slug, category.title) in FURNITURE_CATEGORIES)


class CategoryForm(AutoSlugMixin, forms.ModelForm):
    """Generate a Latin code when creating a category."""

    slug_source = 'title'
    slug = forms.SlugField(
        required=False, max_length=50, label='Код категории',
        help_text='При создании можно оставить пустым: код появится латиницей.',
    )

    class Meta:
        model = Category
        fields = ('title', 'slug')

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = bool(self.instance.pk)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_safe
def category_list(request: HttpRequest) -> HttpResponse:
    """Show categories and the number of assigned products."""
    categories = Category.objects.annotate(product_count=Count('product_items'))
    return render(request, 'products/categories/list.html', {
        'categories': categories,
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_http_methods(['GET', 'POST'])
def category_edit(
    request: HttpRequest, category_id: int | None = None,
) -> HttpResponse:
    """Create or edit a category through a validated form."""
    category = get_object_or_404(Category, pk=category_id) if category_id else None
    is_home_category = _is_home_category(category)
    form = CategoryForm(
        request.POST if request.method == 'POST' else None, instance=category,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        CatalogCache.clear_catalog()
        messages.success(request, 'Категория сохранена.')
        return redirect('catalog:category_list_manage')
    return render(request, 'products/categories/form.html', {
        'form': form, 'category': category, 'is_home_category': is_home_category,
    })


@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_http_methods(['GET', 'POST'])
def category_delete(request: HttpRequest, category_id: int) -> HttpResponse:
    """Delete only empty categories, after explicit POST confirmation."""
    if request.method == 'POST':
        with transaction.atomic():
            category = get_object_or_404(
                Category.objects.select_for_update(), pk=category_id,
            )
            if category.product_items.exists():
                messages.error(
                    request, 'Сначала перенесите изделия в другую категорию.',
                )
            else:
                category.delete()
                transaction.on_commit(CatalogCache.clear_catalog)
                messages.success(request, 'Категория удалена.')
        return redirect('catalog:category_list_manage')
    category = get_object_or_404(Category, pk=category_id)
    return render(request, 'products/categories/delete.html', {
        'category': category, 'product_count': category.product_items.count(),
        'is_home_category': _is_home_category(category),
    })
