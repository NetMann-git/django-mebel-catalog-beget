"""шаг 50: public contact page respects the existing editor and sanitization."""
from django.test import TestCase
from django.urls import reverse
from apps.home.models import ContactSettings


class FurnitureContactPageTests(TestCase):
    def setUp(self):
        self.record, _ = ContactSettings.objects.update_or_create(pk=1, defaults={
            'is_published': True, 'phone_primary': '+7 (900) 123-45-67',
            'phone_secondary': '', 'address': 'Адрес мастерской',
            'map_url': 'https://maps.example.test/workshop',
            'telegram_url': 'https://t.me/example_workshop', 'vk_url': '', 'max_url': ''})
        self.url = reverse('furniture_contacts')

    def test_published_editor_data_and_request_link(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tel:+79001234567')
        self.assertContains(response, self.record.address)
        self.assertContains(response, self.record.map_url)
        self.assertContains(response, self.record.telegram_url)
        self.assertContains(response, 'href="' + reverse('home') + '#callback"')
        self.assertNotContains(response, 'noindex')
        self.assertNotContains(response, 'themes/auto.css')

    def test_unpublished_and_absent_settings_do_not_leak_contacts(self):
        self.record.is_published = False
        self.record.save(update_fields=['is_published'])
        for _ in range(2):
            response = self.client.get(self.url)
            self.assertContains(response, 'Контакты пока не опубликованы')
            for value in [self.record.address, self.record.phone_primary, self.record.map_url, self.record.telegram_url]:
                self.assertNotContains(response, value)
            ContactSettings.objects.filter(pk=1).delete()

    def test_empty_published_record_uses_empty_message(self):
        for field in ['phone_primary', 'address', 'map_url', 'telegram_url']:
            setattr(self.record, field, '')
        self.record.save()
        self.assertContains(self.client.get(self.url), 'Контакты пока не опубликованы')

    def test_map_only_is_visible_and_untrusted_content_is_escaped(self):
        self.record.phone_primary = ''
        self.record.address = ''
        self.record.telegram_url = ''
        self.record.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'Открыть карту')
        self.assertNotContains(response, 'Контакты пока не опубликованы')
        self.record.address = '<script>bad()</script>'
        self.record.map_url = 'javascript:bad()'
        self.record.telegram_url = 'https://user:password@example.test'
        self.record.save()
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;script&gt;bad()')
        for value in ['<script>bad()', 'javascript:bad()', 'user:password']:
            self.assertNotContains(response, value)

    def test_navigation_and_sitemap(self):
        for name in ['home', 'catalog:catalog', 'furniture_about', 'furniture_services']:
            self.assertContains(self.client.get(reverse(name)), 'href="' + self.url + '"', count=2)
        self.assertContains(self.client.get('/'), 'id="callback"')
        self.assertContains(self.client.get('/sitemap-pages.xml'), self.url)
