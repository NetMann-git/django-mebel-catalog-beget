"""Published workshop contacts reuse ContactSettings; legacy seed values stay hidden."""
import re
from urllib.parse import urlsplit
from django import template
from apps.home.models import ContactSettings

register = template.Library()
# Exact defaults from home.0008_seed_contacts, never changed in the database here.
LEGACY_PHONE_DIGITS = {'79885808899', '79289595459'}
LEGACY_TEXT = {
    'address': 'Ростов-на-Дону, Максима Горького 249',
    'map_url': 'https://yandex.ru/map-widget/v1/?z=12&ol=biz&oid=11795644110',
    'telegram_url': 'https://t.me/auto_korea_pod_zakaz',
    'vk_url': 'https://vk.com/podberemauto',
    'max_url': 'https://xn----8sbbggha0dnibq5a.xn--p1ai/max.ru/channel_podberem_auto',
}


def phone_link(value):
    value = (value or '').strip()
    digits = re.sub(r'[^0-9]', '', value)
    comparable = '7' + digits[1:] if len(digits) == 11 and digits.startswith('8') else digits
    if not digits or comparable in LEGACY_PHONE_DIGITS:
        return None
    return {'text': value, 'url': 'tel:' + ('+' if value.startswith('+') else '') + digits}


def public_url(value, field):
    value = (value or '').strip()
    if value.rstrip('/') == LEGACY_TEXT[field].rstrip('/'):
        return ''
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
    if ' '.join(address.casefold().split()) == ' '.join(LEGACY_TEXT['address'].casefold().split()):
        address = ''
    socials = [{'name': label, 'url': url} for field, label in [
        ('telegram_url', 'Telegram'), ('vk_url', 'ВКонтакте'), ('max_url', 'MAX')]
        if (url := public_url(getattr(record, field), field))]
    return {'phones': phones, 'primary': phones[0] if phones else None,
            'address': address, 'map_url': public_url(record.map_url, 'map_url'),
            'socials': socials, 'has_content': bool(phones or address or socials)}


@register.simple_tag(takes_context=True)
def furniture_contacts(context):
    request = context.get('request')
    if request is None:
        return get_contacts()
    if not hasattr(request, '_furniture_public_contacts'):
        request._furniture_public_contacts = get_contacts()
    return request._furniture_public_contacts
