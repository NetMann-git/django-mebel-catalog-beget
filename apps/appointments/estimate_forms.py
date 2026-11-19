"""Shared detailed estimate form for directions, products and completed works."""
from django import forms
from .forms import CarInquiryForm, SimilarProjectForm

DIRECTIONS = [('kuhni', 'Кухни'), ('shkafy', 'Шкафы'), ('garderobnye', 'Гардеробные'), ('stellazhi', 'Стеллажи'), ('polki', 'Полки'), ('drugaya-mebel', 'Другая мебель')]
LAYOUT_CHOICES = [('straight', 'Прямая'), ('corner', 'Угловая'), ('u-shaped', 'П-образная'), ('island', 'С островом')]


class EstimateRequestForm(SimilarProjectForm):
    direction_key = ''
    widget_prefix = 'estimate'
    kitchen_dimensions = False
    direction = forms.ChoiceField(label='Какую мебель хотите?', required=False, choices=[('', 'Помогите определиться')] + DIRECTIONS)
    layout = forms.ChoiceField(label='Планировка кухни (если нужна кухня)', required=False, choices=[('', 'Помогите определиться')] + LAYOUT_CHOICES)
    budget = forms.CharField(label='Ориентир бюджета (необязательно)', required=False, max_length=100, help_text='Можно указать диапазон: это поможет подобрать материалы и наполнение.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].required = False
        self.fields['city'].label = 'Город / населённый пункт (необязательно)'
        self.order_fields(['name', 'phone', 'city', 'email', 'direction', 'layout', 'width_cm', 'height_cm', 'depth_cm', 'budget', 'comment', 'reference_photo'])
        for name, field in self.fields.items():
            field.widget.attrs['id'] = self.widget_prefix + '-' + name
            if field.help_text:
                field.widget.attrs['aria-describedby'] = field.widget.attrs['id'] + '-help'

    def clean(self):
        data = CarInquiryForm.clean(self)
        direction = self.direction_key or data.get('direction', '')
        lines = ['Направление: ' + ('кухни на заказ.' if direction == 'kuhni' else dict(DIRECTIONS)[direction] + '.') ] if direction else []
        if direction == 'kuhni' and data.get('layout'):
            lines.append('Планировка: ' + dict(LAYOUT_CHOICES)[data['layout']] + '.')
        if data.get('budget'):
            lines.append('Ориентир бюджета: ' + data['budget'])
        dimensions = []
        for field, label in [('width_cm', 'ширина'), ('height_cm', 'высота'), ('depth_cm', 'глубина')]:
            if data.get(field) is not None:
                if self.kitchen_dimensions:
                    label = self.fields[field].label.removesuffix(', см') + ':'
                dimensions.append(f'{label} {data[field]} см')
        if dimensions:
            lines.append('Примерные размеры: ' + ', '.join(dimensions) + '.')
        if 'comment' in data:
            data['comment'] = '\n\n'.join(filter(None, ('\n'.join(lines), data['comment'])))
        return data
