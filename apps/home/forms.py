import re
from urllib.parse import urlparse

from django import forms

from .models import ClientShowcase, ContactSettings, TeamMember


class ClientShowcaseForm(forms.ModelForm):
    class Meta:
        model = ClientShowcase
        fields = ("name", "vehicle", "image", "rutube_url", "sort_order", "is_published")
        labels = {"vehicle": "Изделие или проект"}
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например, Александр"}),
            "vehicle": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например, кухня или шкаф для прихожей"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "rutube_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://rutube.ru/video/.../"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


    def clean_rutube_url(self):
        value = (self.cleaned_data.get("rutube_url") or "").strip()
        if not value:
            return ""

        try:
            parsed = urlparse(value)
        except ValueError:
            raise forms.ValidationError("Укажите корректную ссылку Rutube.")

        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"rutube.ru", "www.rutube.ru"}:
            raise forms.ValidationError("Допустима только ссылка на видео с rutube.ru.")

        match = re.search(r"/(?:video|play/embed)/([0-9a-fA-F]{32})(?:/|$)", parsed.path)
        if not match:
            raise forms.ValidationError("Не удалось определить видео Rutube. Вставьте обычную ссылку на видео или embed-ссылку.")

        return f"https://rutube.ru/play/embed/{match.group(1).lower()}/"



class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ("name", "position", "image", "sort_order", "is_published")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например, Иван"}),
            "position": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например, Главный менеджер"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        image = cleaned.get("image")
        has_existing = bool(self.instance and self.instance.pk and self.instance.has_image)
        if image is False:
            self.add_error("image", "У сотрудника должна оставаться фотография. Загрузите новую вместо удаления.")
        elif not image and not has_existing:
            self.add_error("image", "Добавьте фотографию сотрудника.")
        return cleaned


class ContactSettingsForm(forms.ModelForm):
    class Meta:
        model = ContactSettings
        fields = (
            "phone_primary",
            "phone_secondary",
            "address",
            "map_url",
            "telegram_url",
            "vk_url",
            "max_url",
            "is_published",
        )
        widgets = {
            "phone_primary": forms.TextInput(attrs={"class": "form-control", "placeholder": "+7 (988) 580-88-99"}),
            "phone_secondary": forms.TextInput(attrs={"class": "form-control", "placeholder": "+7 (928) 959-54-59"}),
            "address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ростов-на-Дону, Максима Горького 249"}),
            "map_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://yandex.ru/map-widget/v1/...?"}),
            "telegram_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://t.me/..."}),
            "vk_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://vk.com/..."}),
            "max_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://max.ru/..."}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_map_url(self):
        value = (self.cleaned_data.get("map_url") or "").strip()
        if not value:
            raise forms.ValidationError("Укажите ссылку на карту.")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise forms.ValidationError("Ссылка на карту должна начинаться с http:// или https://.")
        return value
