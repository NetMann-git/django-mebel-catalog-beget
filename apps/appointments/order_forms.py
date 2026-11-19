from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import WorkshopOrder


class OrderForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput, min_value=1)

    class Meta:
        model = WorkshopOrder
        fields = ('title','client_name','phone','email','city','specification','stage','responsible','due_on','agreed_total','paid','note')
        widgets = {
            'specification':forms.Textarea(attrs={'rows':6}),
            'note':forms.Textarea(attrs={'rows':4}),
            'due_on':forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revision'].initial = self.instance.revision
        allowed = Q(is_active=True) & (Q(is_superuser=True) | Q(profile__role__in=['manager','admin']))
        if self.instance.responsible_id:
            allowed |= Q(pk=self.instance.responsible_id)
        self.fields['responsible'].queryset = get_user_model().objects.filter(allowed).distinct().order_by('username')
        self.fields['agreed_total'].help_text = 'Оставьте пустым, пока стоимость не согласована с клиентом.'
        self.fields['paid'].help_text = 'Общая фактически полученная сумма. Изменение сохраняется в истории заказа.'
