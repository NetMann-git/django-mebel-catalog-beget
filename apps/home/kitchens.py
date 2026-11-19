"""Kitchen service page and a brief using the existing inquiry workflow."""
from django import forms
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.appointments.forms import CarInquiryForm, SimilarProjectForm
from apps.appointments.models import CallbackReferencePhoto
from apps.appointments.views import _notify_saved_inquiry
from apps.products.models import Category, Product
from .portfolio import portfolio_projects

LAYOUTS = (
    ('straight', 'Прямая', 'Один ряд вдоль стены. Подходит для вытянутой кухни или компактной рабочей зоны.'),
    ('corner', 'Угловая', 'Два смежных ряда. Важно проверить доступ к углу и открывание соседних секций.'),
    ('u-shaped', 'П-образная', 'Три рабочих стороны. Нужен свободный проход между рядами мебели.'),
    ('island', 'С островом', 'Дополнительная рабочая зона. Проверим проходы, коммуникации и расположение техники.'),
)


class KitchenRequestForm(SimilarProjectForm):
    layout = forms.ChoiceField(
        label='Планировка', required=False,
        choices=[('', 'Помогите определиться')] + [(key, title) for key, title, _ in LAYOUTS],
    )
    budget = forms.CharField(
        label='Ориентир бюджета (необязательно)', required=False, max_length=100,
        help_text='Можно указать диапазон: это поможет подобрать материалы и наполнение.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].required = False
        self.fields['city'].label = 'Город / населённый пункт (необязательно)'
        self.fields['width_cm'].label = 'Длина основного ряда, см'
        self.fields['width_cm'].help_text = 'Для угловой или П-образной кухни укажите остальные стороны в пожеланиях.'
        self.fields['height_cm'].label = 'Высота помещения, см'
        self.fields['depth_cm'].label = 'Желаемая глубина мебели, см'
        self.fields['comment'].label = 'Пожелания к кухне (необязательно)'
        self.fields['comment'].widget.attrs['placeholder'] = 'Другие стороны кухни, материалы, техника, что важно учесть'
        self.order_fields(['name', 'phone', 'city', 'email', 'layout', 'width_cm', 'height_cm', 'depth_cm', 'budget', 'comment', 'reference_photo'])
        for name, field in self.fields.items():
            field.widget.attrs['id'] = 'kitchen-' + name
            if field.help_text:
                field.widget.attrs['aria-describedby'] = 'kitchen-' + name + '-help'

    def clean(self):
        data = CarInquiryForm.clean(self)
        lines = ['Направление: кухни на заказ.']
        if data.get('layout'):
            lines.append('Планировка: ' + dict(self.fields['layout'].choices)[data['layout']] + '.')
        if data.get('budget'):
            lines.append('Ориентир бюджета: ' + data['budget'])
        dimensions = [f"{self.fields[field].label.removesuffix(', см')}: {data[field]} см" for field in ('width_cm', 'height_cm', 'depth_cm') if data.get(field) is not None]
        if dimensions:
            lines.append('Примерные размеры: ' + '; '.join(dimensions) + '.')
        if 'comment' in data:
            data['comment'] = '\n'.join(lines) + '\n\n' + data['comment']
        return data


@require_http_methods(['GET', 'HEAD', 'POST'])
def kitchens(request):
    initial = {'layout': request.GET.get('layout')} if request.GET.get('layout') in dict((k, t) for k, t, _ in LAYOUTS) else {}
    form = KitchenRequestForm(request.POST, request.FILES) if request.method == 'POST' else KitchenRequestForm(initial=initial)
    if request.method == 'POST':
        if request.POST.get('website', '').strip():
            return redirect(reverse('furniture_kitchens') + '#kitchen-request')
        if form.is_valid():
            inquiry = form.save(commit=False)
            inquiry.source = 'site_callback'
            with transaction.atomic():
                inquiry.save()
                if photo := form.cleaned_data.get('reference_photo'):
                    CallbackReferencePhoto.objects.create(callback=inquiry, content=photo)
            _notify_saved_inquiry(inquiry)
            request.session['kitchen_request_success'] = inquiry.pk
            return redirect(reverse('furniture_kitchens') + '#kitchen-request')

    if request.method == 'POST':
        for name in form.errors:
            if name in form.fields:
                widget = form.fields[name].widget
                widget.attrs['aria-invalid'] = 'true'
                widget.attrs['aria-describedby'] = ' '.join(filter(None, (
                    widget.attrs.get('aria-describedby'), 'kitchen-' + name + '-error',
                )))

    category = Category.objects.filter(slug='kuhni').first()
    completed = list(portfolio_projects().filter(category__slug='kuhni')[:3])
    examples = Product.objects.filter(is_active=True, category=category).exclude(pk__in=[product.pk for product in completed]).exclude(image='').exclude(image__isnull=True).select_related('category').prefetch_related('badges').order_by('-is_featured', '-pk')[:6] if category else []
    return render(request, 'home/kitchens.html', {
        'kitchen_form': form, 'kitchen_layouts': LAYOUTS,
        'kitchen_examples': examples,
        'kitchen_portfolio': completed,
        'kitchen_catalog_url': reverse('catalog:catalog') + (f'?category={category.pk}' if category else ''),
        'kitchen_success_id': request.session.pop('kitchen_request_success', None),
        'kitchen_canonical': request.build_absolute_uri(reverse('furniture_kitchens')),
    }, status=400 if request.method == 'POST' else 200)
