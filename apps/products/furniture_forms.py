"""Furniture editors reuse existing validation without changing stored legacy data."""
from django import forms

from .car_model_forms import ProductModelForm
from .forms import ProductForm
from .equipment_forms import EquipmentCheckboxes, EquipmentChoiceField
from .models import EquipmentOption


class FurnitureFieldsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('car_model', None)
        if 'title' in self.fields:
            self.fields['title'].label = 'Название изделия'
            self.fields['title'].widget.attrs['placeholder'] = 'Например, шкаф для прихожей'
        if 'brand' in self.fields and self.instance.car_model_id:
            # Keep the hidden legacy model/brand relationship valid. Never clear it
            # or let a forged POST replace its brand through the furniture form.
            self.fields['brand'].disabled = True
            self.fields['brand'].help_text = 'Поле связано с сохранёнными данными и доступно только для просмотра.'
        if 'badges' in self.fields:
            self.fields['badges'].label = 'Метки изделия'
        if 'product_type' in self.fields:
            self.fields['product_type'].label = 'Тип изделия'
            self.fields['product_type'].widget = forms.TextInput(attrs={'class': 'form-control'})
        if 'equipment' in self.fields:
            self.fields['equipment'].help_text = 'Выберите согласованные особенности изделия из справочника комплектации.'

    class Media:
        extend = False
        css = {'all': ('products/css/equipment.css',)}
        js = ('products/js/manager_slug.js',)


class FurnitureProductForm(FurnitureFieldsMixin, ProductForm):
    """Manager form, with grouped selections and no vehicle source codes."""
    equipment = EquipmentChoiceField(
        queryset=EquipmentOption.objects.none(),
        required=False, label='Комплектация',
        widget=EquipmentCheckboxes(attrs={'form': 'product-form'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['equipment'].queryset = self.fields['equipment'].queryset.order_by(
            'group__sort_order', 'group__name', 'sort_order', 'name', 'pk',
        )


class FurnitureAdminForm(FurnitureFieldsMixin, ProductModelForm):
    """Admin form keeps the existing URL, equipment and model validation."""
