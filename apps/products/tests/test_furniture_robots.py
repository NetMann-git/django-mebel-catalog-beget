"""шаг 23: crawl rules, sitemap discovery, methods and no database reads."""
from urllib.robotparser import RobotFileParser

from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class FurnitureRobotsTests(SimpleTestCase):
    def parser(self):
        response = self.client.get(reverse('robots_txt'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        text = response.content.decode('utf-8')
        self.assertNotIn('<html', text)
        parser = RobotFileParser()
        parser.parse(text.splitlines())
        return parser

    def test_public_pages_and_assets_are_allowed_for_crawling(self):
        parser = self.parser()
        for agent in ['*', 'Googlebot', 'YandexBot']:
            for path in ['/', '/catalog/', '/catalog/oak-case/', '/catalog/brand/workshop/',
                         '/static/home/css/furniture.css', '/media/products/original.jpg',
                         '/sitemap.xml', '/sitemap-products.xml', '/privacy/']:
                with self.subTest(agent=agent, path=path):
                    self.assertTrue(parser.can_fetch(agent, 'http://testserver' + path))

    def test_service_sections_are_excluded_including_nested_paths(self):
        parser = self.parser()
        for agent in ['*', 'Googlebot', 'YandexBot']:
            for path in ['/admin/', '/admin/products/product/', '/account/login/',
                         '/account/manager/', '/catalog/manage/', '/catalog/manage/1/edit/',
                         '/search/?q=oak', '/wishlist/', '/catalog/comparison/',
                         '/catalog/recently-viewed/']:
                with self.subTest(agent=agent, path=path):
                    self.assertFalse(parser.can_fetch(agent, 'http://testserver' + path))
        self.assertEqual(parser.site_maps(), ['http://testserver/sitemap.xml'])

    @override_settings(ALLOWED_HOSTS=['127.0.0.1', 'lustrid.ru'])
    def test_sitemap_uses_current_host_port_and_scheme(self):
        for host, secure, expected in [('127.0.0.1:8000', False, 'http://127.0.0.1:8000/sitemap.xml'),
                                       ('lustrid.ru', True, 'https://lustrid.ru/sitemap.xml')]:
            response = self.client.get(reverse('robots_txt'), HTTP_HOST=host, secure=secure)
            self.assertEqual(response.status_code, 200)
            parser = RobotFileParser()
            parser.parse(response.content.decode().splitlines())
            self.assertEqual(parser.site_maps(), [expected])

    def test_head_is_supported_and_writes_are_rejected(self):
        response = self.client.head(reverse('robots_txt'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        for method in ['post', 'put', 'patch', 'delete']:
            self.assertEqual(getattr(self.client, method)(reverse('robots_txt')).status_code, 405)
