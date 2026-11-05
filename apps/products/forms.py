# apps/products/forms.py
from django import forms
from django.utils.html import format_html
from .image_variants import image_variant
from .models import Product, ProductGalleryImage, Badge, Brand
from .manager_slugs import AutoSlugMixin
from .car_model_forms import ProductModelForm
from .equipment_forms import CompactEquipmentCheckboxes, CompactEquipmentChoiceField
from .models import EquipmentOption
from django.db.models import F


class ImagePreviewWidget(forms.ClearableFileInput):
    """Виджет для отображения текущего изображения."""
    
    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs, renderer)
        
        if value and hasattr(value, 'url'):
            preview_html = format_html('''
                <div style="margin-bottom: 10px;">
                    <img class="image-preview-thumbnail" src="{}" alt="Текущее изображение" style="max-width: 200px; max-height: 200px; border-radius: 4px; border: 1px solid #ddd;">
                    <p style="font-size: 12px; color: #999; margin-top: 5px;">Текущее изображение</p>
                </div>
            ''', image_variant(value, 'form_thumb'))
            return format_html('{}{}', preview_html, html)
        
        return html


class ProductForm(AutoSlugMixin, ProductModelForm):
    """Форма для создания и редактирования товара."""
    
    equipment = CompactEquipmentChoiceField(
        queryset=EquipmentOption.objects.none(), required=False,
        widget=CompactEquipmentCheckboxes(attrs={'form': 'product-form'}),
        label='Комплектация',
        help_text='Отметьте известные опции. Без отметки — наличие не указано.',
    )

    slug_source = "title"
    slug = forms.SlugField(
        required=False, label="URL (slug)",
        help_text="Заполняется латиницей автоматически. Можно изменить до сохранения.",
    )

    # Поле для бейджей - чекбоксы
    badges = forms.ModelMultipleChoiceField(
        queryset=Badge.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'badges-checkbox'}),
        label='Бейджи'
    )
    
    class Meta:
        model = Product
        fields = [
            'title', 'slug', 'category', 'brand', 'car_model', 'price', 'currency',
            'short_description', 'description', 'is_active', 'is_featured',
            'availability_status', 'article', 'product_type', 'meta_title', 'meta_description',
            'badges', 'equipment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Название товара',
                'id': 'id_title',
                'data-slug-source': 'true'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'url-адрес (автозаполнение)',
                'id': 'id_slug',
                'data-slug-target': 'true'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'short_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'availability_status': forms.Select(attrs={'class': 'form-control'}),
            'article': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Артикул'}),
            'product_type': forms.Select(attrs={'class': 'form-control'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SEO заголовок'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['badges'].initial = self.instance.badges.all()
            self.fields['slug'].required = False
        self.fields['equipment'].queryset = self.fields['equipment'].queryset.order_by(
            F('encar_standard_code').asc(nulls_last=True), 'name', 'pk',
        )
        self.fields['slug'].widget.attrs['class'] = 'form-control'
        if self.instance.pk:
            listing_ids = list(self.instance.import_sources.filter(
                source='encar',
            ).values_list('listing_id', flat=True))
            if len(listing_ids) == 1:
                self.fields['article'].disabled = True
                self.initial['article'] = listing_ids[0]
                self.fields['article'].help_text = (
                    'Артикул совпадает с ID исходного объявления Encar. '
                    'Внутренний ID автомобиля хранится отдельно.'
                )
    
    def clean_slug(self) -> str:
        """Defer URL approval to the shared product form."""
        return self.instance.slug if self.instance.pk else ''

    def clean_article(self):
        """Keep the linked listing ID without silently taking another article."""
        article = self.cleaned_data.get('article', '')
        if self.fields['article'].disabled and self.instance.article != article and Product.objects.filter(
            article=article,
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                'ID Encar уже используется как артикул другой карточки. '
                'Сначала устраните конфликт.'
            )
        return article

    def save(self, commit=True):
        product = super().save(commit=False)
        if commit:
            product.save()
            self.save_m2m()
            product.badges.set(self.cleaned_data['badges'])
        return product
    


class BrandForm(AutoSlugMixin, forms.ModelForm):
    """Форма управления брендом для менеджера."""

    slug_source = "name"
    slug = forms.SlugField(
        required=False, label="URL (slug)",
        help_text="Заполняется латиницей автоматически. Можно изменить до сохранения.",
    )

    class Meta:
        model = Brand
        fields = [
            "name", "slug", "logo", "description", "country", "sort_order",
            "meta_title", "meta_description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control", "data-slug-source": "true",
            }),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "logo": ImagePreviewWidget(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "meta_title": forms.TextInput(attrs={"class": "form-control"}),
            "meta_description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["slug"].required = True
        self.fields["slug"].widget.attrs.update({
            "class": "form-control", "data-slug-target": "true",
        })


# ДОБАВИТЬ ЭТУ ФОРМУ
class GalleryImageForm(forms.ModelForm):
    """Форма для добавления изображений в галерею."""
    
    class Meta:
        model = ProductGalleryImage
        fields = ['image', 'alt']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'alt': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Описание изображения'}),
        }
