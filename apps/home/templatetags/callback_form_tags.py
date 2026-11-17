from django import template

from apps.appointments.forms import CallbackRequestForm

register = template.Library()


@register.simple_tag
def callback_request_form():
    return CallbackRequestForm()
