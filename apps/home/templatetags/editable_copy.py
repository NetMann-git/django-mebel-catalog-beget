from django import template
from apps.home.editable_copy import page_text

register=template.Library()


@register.simple_tag(takes_context=True)
def editable_copy(context,key):
    return page_text(key,context.get('request'))
