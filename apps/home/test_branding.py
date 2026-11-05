"""Шаг 63: общие логотипы, favicon и содержимое комплекта."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.staticfiles import finders
from PIL import Image


class BrandingPagesTests(TestCase):
    def test_public_pages_and_account_have_single_icon_set(self):
        from apps.products.models import Product
        p = Product.objects.create(title='Шкаф', slug='brand-check', price=100)
        for url in ['/', '/catalog/', p.get_absolute_url(), '/services/', '/materials/',
                    '/contacts/', '/about/', '/privacy/', '/account/login/', '/admin/login/']:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, 'home/branding/favicon.svg', count=1)
                self.assertContains(r, 'home/branding/favicon.ico', count=1)
                self.assertContains(r, 'home/branding/apple-touch-icon.png', count=1)
                self.assertContains(r, 'home/branding/site.webmanifest', count=1)
                self.assertNotContains(r, 'home/images/logo.png')
        r = self.client.get('/')
        self.assertContains(r, 'home/branding/logo-compact-dark.svg')
        self.assertContains(r, 'home/branding/logo-full-light.svg')

    @override_settings(STATIC_URL='/assets/')
    def test_automatic_browser_requests_follow_configured_static_url(self):
        for filename in ['favicon.ico', 'apple-touch-icon.png']:
            r = self.client.get('/' + filename)
            self.assertEqual(r.status_code, 301)
            self.assertEqual(r['Location'], '/assets/home/branding/' + filename)


class BrandingFilesTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(finders.find('home/branding/favicon.svg')).parent

    def test_ico_has_multiple_resolutions_and_png_sizes(self):
        with Image.open(self.root / 'favicon.ico') as im:
            self.assertEqual(im.ico.sizes(), {(16,16),(24,24),(32,32),(48,48),(64,64)})
        for name, size in [('apple-touch-icon.png',180),('apple-touch-icon-167x167.png',167),
                           ('apple-touch-icon-152x152.png',152),('android-chrome-192x192.png',192),
                           ('android-chrome-512x512.png',512),('maskable-icon-512x512.png',512),
                           ('favicon-16x16.png',16),('favicon-32x32.png',32)]:
            with Image.open(self.root / name) as im:
                self.assertEqual(im.size, (size,size))

    def test_manifest_targets_exist_and_logos_use_outlined_text(self):
        manifest = json.loads((self.root / 'site.webmanifest').read_text())
        self.assertEqual(manifest['start_url'], '/')
        for item in manifest['icons']:
            self.assertTrue((self.root / item['src']).is_file())
        for name in ['full-dark','compact-dark','full-light','compact-light']:
            svg = ET.parse(self.root / ('logo-' + name + '.svg'))
            self.assertEqual(svg.getroot().get('viewBox'), '0 0 525 110')
            self.assertFalse(svg.findall('.//{http://www.w3.org/2000/svg}text'))
            with Image.open(self.root / ('logo-' + name + '.png')) as im:
                self.assertEqual(im.size, (1575,330))
                self.assertEqual(im.mode, 'RGBA')
