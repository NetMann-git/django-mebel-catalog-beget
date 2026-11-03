"""Manager's editor for all attributes belonging to one product."""

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Product, ProductAttribute
from .product_attribute_forms import ProductAttributeForm


class ProductAttributeFormSet(BaseInlineFormSet):
    """Reject identifiers that do not belong to the edited product."""

    def clean(self) -> None:
        super().clean()
        for form in self.forms:
            record = form.cleaned_data.get('id')
            if record and record.product_id != self.instance.pk:
                raise forms.ValidationError(
                    'Характеристика принадлежит другому изделию.',
                )


ManagerAttributeFormSet = inlineformset_factory(
    Product, ProductAttribute,
    form=ProductAttributeForm,
    formset=ProductAttributeFormSet,
    fields=('attribute_type', 'attribute_value', 'free_value', 'sort_order'),
    extra=1, can_delete=True,
)
