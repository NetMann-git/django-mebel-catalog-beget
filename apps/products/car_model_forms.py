"""Shared model selector for manager and admin product editors."""

from typing import Any

from django import forms

from .manager_slugs import AutoSlugMixin, unique_slug
from .models import CarModel, Product, EquipmentOption
from .equipment_forms import (
    EquipmentCheckboxes, EquipmentChoiceField, EquipmentFormMixin,
)


class CarModelSelect(forms.Select):
    """Expose manufacturer identifiers for the dependent select."""

    def create_option(self, *args: Any, **kwargs: Any) -> dict:
        option = super().create_option(*args, **kwargs)
        value = option['value']
        if hasattr(value, 'instance'):
            option['attrs']['data-brand'] = str(value.instance.brand_id)
        return option


class ProductModelForm(EquipmentFormMixin, forms.ModelForm):
    """Keep server-side model validation available without JavaScript."""

    equipment = EquipmentChoiceField(
        queryset=EquipmentOption.objects.none(), required=False,
        widget=EquipmentCheckboxes, label='Комплектация',
        help_text='Отметьте известные опции. Без отметки — наличие не указано.',
    )

    car_model = forms.ModelChoiceField(
        queryset=CarModel.objects.select_related('brand'), required=False,
        label='Модель автомобиля',
        help_text='Сначала выберите марку. Если модели нет, добавьте её в справочник моделей.',
        widget=CarModelSelect(attrs={
            'class': 'form-control', 'data-car-model-select': '',
        }),
    )

    slug = forms.SlugField(
        required=False, label='URL',
        widget=forms.TextInput(attrs={'readonly': True}),
        help_text='Автоматически формируется из названия при сохранении.',
    )

    regenerate_slug = forms.BooleanField(
        required=False, label='Обновить URL из названия',
        help_text='Только с этой отметкой существующий адрес изменится. '
                  'Прежние ссылки после смены адреса перестанут открывать карточку.',
        widget=forms.CheckboxInput(attrs={'data-slug-approve': 'true'}),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if 'title' in self.fields:
            self.fields['title'].widget.attrs['data-slug-source'] = 'true'
        if 'slug' in self.fields:
            self.fields['slug'].widget.attrs.update({
                'data-slug-target': 'true', 'readonly': True,
                'data-slug-existing': 'true' if self.instance.pk else 'false',
            })
            self.fields['slug'].help_text = (
                'Новая карточка: адрес формируется автоматически. '
                'Существующая: только после отметки «Обновить URL из названия».'
            )
        if 'regenerate_slug' in self.fields and 'slug' in self.fields:
            names = list(self.fields)
            names.remove('regenerate_slug')
            names.insert(names.index('slug') + 1, 'regenerate_slug')
            self.order_fields(names)

    def clean_slug(self) -> str:
        """Ignore a forged URL; approval is evaluated after all fields."""
        return self.instance.slug if self.instance.pk else ''

    def clean(self) -> dict:
        """Generate URLs only for new cards or with explicit approval."""
        cleaned = super().clean()
        if not self.instance.pk or cleaned.get('regenerate_slug'):
            if cleaned.get('title'):
                cleaned['slug'] = unique_slug(
                    Product, cleaned['title'], exclude_pk=self.instance.pk,
                )
        else:
            cleaned['slug'] = self.instance.slug
        return cleaned

    class Meta:
        model = Product
        fields = '__all__'

    class Media:
        js = ('products/js/car-model-select.js', 'products/js/manager_slug.js')


class CarModelForm(AutoSlugMixin, forms.ModelForm):
    """Create Latin model codes using the existing manager convention."""

    slug_source = 'name'
    slug = forms.SlugField(
        required=False, label='Код модели',
        help_text='Автоматически формируется латиницей, если оставить пустым.',
    )

    class Meta:
        model = CarModel
        fields = ('brand', 'name', 'slug', 'sort_order')

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['slug'].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        if self.instance.pk and self.instance.products.exists():
            self.fields['brand'].disabled = True
            self.fields['brand'].help_text = 'Марка закреплена: модель используется в товарах.'

    def clean(self) -> dict:
        """Prevent duplicate model names within a brand in normal editors."""
        cleaned = super().clean()
        brand, name = cleaned.get('brand'), cleaned.get('name')
        if brand and name and CarModel.objects.filter(
            brand=brand, name__iexact=name,
        ).exclude(pk=self.instance.pk).exists():
            self.add_error('name', 'Такая модель у этой марки уже существует.')
        return cleaned
