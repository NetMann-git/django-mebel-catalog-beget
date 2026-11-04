"""Published workshop contacts reuse the existing ContactSettings record."""
import re
from urllib.parse import urlsplit
from django import template
from apps.home.models import ContactSettings

register = template.Library()


def phone_link(value):
    value = (value or '').strip()
    digits = re.sub(r'[^0-9]', '', value)
    if not digits:
        return None
    return {'text': value, 'url': 'tel:' + ('+' if value.startswith('+') else '') + digits}


def public_url(value):
    value = (value or '').strip()
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme.lower() in {'http', 'https'} and parsed.hostname and not parsed.username and not parsed.password else ''
    except ValueError:
        return ''


def get_contacts():
    record = ContactSettings.objects.filter(pk=1, is_published=True).first()
    if not record:
        return {}
    phones = [phone for phone in [phone_link(record.phone_primary), phone_link(record.phone_secondary)] if phone]
    address = (record.address or '').strip()
    socials = [{'name': label, 'url': url} for field, label in [
        ('telegram_url', 'Telegram'), ('vk_url', 'ВКонтакте'), ('max_url', 'MAX')]
        if (url := public_url(getattr(record, field)))]
    map_url = public_url(record.map_url)
    return {'phones': phones, 'primary': phones[0] if phones else None,
            'address': address, 'map_url': map_url,
            'socials': socials, 'has_content': bool(phones or address or socials or map_url)}


@register.simple_tag(takes_context=True)
def furniture_contacts(context):
    request = context.get('request')
    if request is None:
        return get_contacts()
    if not hasattr(request, '_furniture_public_contacts'):
        request._furniture_public_contacts = get_contacts()
    return request._furniture_public_contacts
