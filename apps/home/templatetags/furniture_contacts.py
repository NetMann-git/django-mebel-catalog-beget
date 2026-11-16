"""Published workshop contacts reuse the existing ContactSettings record."""
import re
from urllib.parse import urlsplit
from django import template
from apps.home.contact_links import public_url
from apps.home.models import ContactSettings

register = template.Library()

# These accounts came from the original automotive catalog.
LEGACY_SOCIAL_ACCOUNTS = {
    ('t.me', '/auto_korea_pod_zakaz'),
    ('vk.com', '/podberemauto'),
    ('xn----8sbbggha0dnibq5a.xn--p1ai', '/max.ru/channel_podberem_auto'),
    ('max.ru', '/channel_podberem_auto'),
}


def phone_link(value):
    value = (value or '').strip()
    digits = re.sub(r'[^0-9]', '', value)
    if not digits:
        return None
    return {'text': value, 'url': 'tel:' + ('+' if value.startswith('+') else '') + digits}


def public_social_url(value):
    url = public_url(value)
    if not url:
        return ''
    parsed = urlsplit(url)
    account = (parsed.hostname, parsed.path.rstrip('/').casefold())
    return '' if account in LEGACY_SOCIAL_ACCOUNTS else url


def get_contacts():
    record = ContactSettings.objects.filter(pk=1, is_published=True).first()
    if not record:
        return {}
    phones = [phone for phone in [phone_link(record.phone_primary), phone_link(record.phone_secondary)] if phone]
    address = (record.address or '').strip()
    socials = [{'name': label, 'url': url} for field, label in [
        ('telegram_url', 'Telegram'), ('vk_url', 'ВКонтакте'), ('max_url', 'MAX')]
        if (url := public_social_url(getattr(record, field)))]
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
