# apps/appointments/forms.py

from django import forms
from .models import Appointment, CallbackRequest


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ('product', 'name', 'phone', 'email', 'date', 'time', 'comment')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'date-picker'}),
            'time': forms.Select(attrs={'class': 'time-select', 'disabled': 'disabled'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Дополнительные пожелания...'}),
            'product': forms.HiddenInput(),
        }
        labels = {
            'name': 'Ваше имя',
            'phone': 'Телефон',
            'email': 'Email',
            'date': 'Дата консультации',
            'time': 'Время консультации',
            'comment': 'Комментарий',
        }
        help_texts = {
            'phone': 'Например: +7 (999) 123-45-67',
            'email': 'Не обязательно, но мы пришлём подтверждение',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Поле time будет заполняться через AJAX, пока оно disabled
        self.fields['time'].widget.attrs['disabled'] = 'disabled'

class CallbackRequestForm(forms.ModelForm):
    """Короткая форма обратного звонка для главной страницы."""

    class Meta:
        model = CallbackRequest
        fields = ('name', 'phone', 'comment')
        widgets = {
            'comment': forms.Textarea(attrs={
                'id': 'callback-comment',
                'rows': 3,
                'placeholder': 'Например: шкаф в прихожую, ширина 180 см, светлые фасады',
            }),
            'name': forms.TextInput(attrs={
                'class': 'home-callback__input',
                'id': 'callback-name',
                'autocomplete': 'name',
                'placeholder': 'Ваше имя',
                'maxlength': 100,
            }),
            'phone': forms.TextInput(attrs={
                'class': 'home-callback__input',
                'id': 'callback-phone',
                'autocomplete': 'tel',
                'inputmode': 'tel',
                'placeholder': 'Номер тел.',
                'maxlength': 30,
            }),
        }

    def clean_name(self):
        return self.cleaned_data.get('name', '').strip()

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) < 10:
            raise forms.ValidationError('Введите корректный номер телефона.')
        if len(digits) > 15:
            raise forms.ValidationError('Номер телефона слишком длинный.')
        return phone


class CarInquiryForm(CallbackRequestForm):
    """Контакты для обсуждения изготовления выбранного изделия."""

    name = forms.CharField(max_length=100, label='Ваше имя')
    city = forms.CharField(max_length=120, label='Город / населённый пункт')

    class Meta:
        model = CallbackRequest
        fields = ('name', 'phone', 'city', 'email', 'comment')
        widgets = {
            'phone': forms.TextInput(attrs={
                'autocomplete': 'tel',
                'inputmode': 'tel',
                'placeholder': '+7 (999) 123-45-67',
            }),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'comment': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Размеры, материалы и пожелания (необязательно)',
            }),
        }
        labels = {
            'phone': 'Телефон',
            'email': 'Электронная почта (необязательно)',
            'comment': 'Комментарий (необязательно)',
        }

class CallbackWorkflowForm(forms.ModelForm):
    """Only the manager can update the follow-up plan."""

    class Meta:
        model = CallbackRequest
        fields = ('status', 'follow_up_on', 'manager_note')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Older clients of the status endpoint submit only the status.
        if self.is_bound:
            for name in ('follow_up_on', 'manager_note'):
                if name not in self.data:
                    del self.fields[name]


class SimilarProjectForm(CarInquiryForm):
    width_cm = forms.IntegerField(label='Ширина, см', required=False, min_value=1, max_value=10000)
    height_cm = forms.IntegerField(label='Высота, см', required=False, min_value=1, max_value=10000)
    depth_cm = forms.IntegerField(label='Глубина, см', required=False, min_value=1, max_value=10000)
    reference_photo = forms.FileField(
        label='Фото помещения или эскиз (необязательно)',
        required=False,
        help_text='JPG, PNG или WebP, до 5 МБ.',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )

    def clean(self):
        data = super().clean()
        dimensions = [
            f'{label} {data[field]} см'
            for field, label in (
                ('width_cm', 'ширина'), ('height_cm', 'высота'), ('depth_cm', 'глубина'),
            )
            if data.get(field) is not None
        ]
        if dimensions and 'comment' in data:
            summary = 'Примерные размеры: ' + ', '.join(dimensions) + '.'
            data['comment'] = '\n\n'.join(filter(None, (summary, data['comment'])))
        return data

    def clean_reference_photo(self):
        from io import BytesIO

        from PIL import Image, ImageOps

        upload = self.cleaned_data['reference_photo']
        if not upload:
            return None
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Размер файла должен быть не больше 5 МБ.')
        try:
            with Image.open(upload) as image:
                if (image.format not in ('JPEG', 'PNG', 'WEBP')
                        or image.width * image.height > 24_000_000
                        or getattr(image, 'is_animated', False)):
                    raise ValueError
                image.thumbnail((1600, 1600))
                result = BytesIO()
                ImageOps.exif_transpose(image).convert('RGB').save(result, format='JPEG', quality=85)
                return result.getvalue()
        except (OSError, ValueError, Image.DecompressionBombError):
            raise forms.ValidationError('Загрузите обычное фото JPG, PNG или WebP размером до 24 мегапикселей.')
