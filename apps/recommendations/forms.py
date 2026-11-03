# apps/recommendations/forms.py

from django import forms
from .models import PromotedProduct

class PromotedProductForm(forms.ModelForm):
    class Meta:
        model = PromotedProduct
        fields = ['product', 'page', 'priority', 'is_active', 'start_date', 'end_date']
        labels = {'product': 'Изделие', 'is_active': 'Рекомендация включена'}
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1', 'class': 'form-control'}),
            'end_date': forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1', 'class': 'form-control'}),
        }
    def clean(self):
        cleaned = super().clean()
        # Browser datetime-local displays seconds; an unchanged field must not
        # silently discard fractional seconds from an existing schedule.
        if self.instance.pk:
            for name in ('start_date', 'end_date'):
                original = getattr(self.instance, name)
                entered = cleaned.get(name)
                if original and entered and entered == original.replace(microsecond=0):
                    cleaned[name] = original
        return cleaned
