"""шаг 22: sitemap selection, publication changes, pagination and hosts."""
from unittest.mock import patch
from urllib.parse import urlsplit
from xml.etree import ElementTree

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.products.models import Brand, Product
from apps.products.sitemaps import ProductSitemap


class FurnitureSitemapTests(TestCase):
    namespace = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

    def setUp(self):
        self.brand = Brand.objects.create(name='Мастерская', slug='workshop')
        self.empty_brand = Brand.objects.create(name='Пустой бренд', slug='empty-workshop')
        self.product = Product.objects.create(title='Шкаф', slug='oak-case', price=100, brand=self.brand)
        self.hidden = Product.objects.create(title='Скрытый', slug='private-case', price=1, is_active=False)

    def locations(self, url, **kwargs):
        response = self.client.get(url, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        return [node.text for node in ElementTree.fromstring(response.content).findall('.//s:loc', self.namespace)]

    def test_index_sections_and_every_listed_page_are_public(self):
        sections = self.locations(reverse('sitemap'))
        self.assertEqual(set(sections), {'http://testserver/sitemap-pages.xml',
                                        'http://testserver/sitemap-products.xml',
                                        'http://testserver/sitemap-brands.xml'})
        urls = []
        for section in sections:
            urls.extend(self.locations(urlsplit(section).path))
        expected = ['/', reverse('catalog:catalog'), reverse('furniture_services'), reverse('furniture_materials'), reverse('furniture_reviews'), reverse('furniture_about'), reverse('furniture_contacts'), reverse('furniture_portfolio'), self.product.get_absolute_url(),
                    self.brand.get_absolute_url(), self.empty_brand.get_absolute_url()]
        self.assertEqual(set(urls), {'http://testserver' + path for path in expected})
        self.assertEqual(len(urls), len(expected))
        for url in urls:
            self.assertEqual(self.client.get(urlsplit(url).path).status_code, 200)
        for private in ['/admin/', '/account/', '/catalog/manage/', '/wishlist/',
                        '/calculator/', '/search/', self.hidden.get_absolute_url()]:
            self.assertNotIn('http://testserver' + private, urls)
        self.assertEqual(Product.objects.count(), 2)

    def test_publication_changes_are_reflected_without_cache_or_data_changes(self):
        url = reverse('sitemap_section', args=['products'])
        self.assertEqual(self.locations(url), ['http://testserver' + self.product.get_absolute_url()])
        self.product.is_active = False
        self.product.save(update_fields=['is_active'])
        self.assertEqual(self.locations(url), [])
        self.hidden.is_active = True
        self.hidden.save(update_fields=['is_active'])
        self.assertEqual(self.locations(url), ['http://testserver' + self.hidden.get_absolute_url()])

    def test_pagination_exposes_all_products_once(self):
        for i in range(4):
            Product.objects.create(title=f'Стол {i}', slug=f'table-{i}', price=10)
        with patch.object(ProductSitemap, 'limit', 2):
            sections = self.locations(reverse('sitemap'))
            product_pages = [url for url in sections if '/sitemap-products.xml' in url]
            self.assertEqual(len(product_pages), 3)
            urls = []
            for url in product_pages:
                parts = urlsplit(url)
                urls.extend(self.locations(parts.path + ('?' + parts.query if parts.query else '')))
            self.assertEqual(len(urls), 5)
            self.assertEqual(len(set(urls)), 5)
            self.assertNotIn('http://testserver' + self.hidden.get_absolute_url(), urls)

    @override_settings(ALLOWED_HOSTS=['localhost', 'lustrid.ru'])
    def test_request_host_and_protocol_are_used_instead_of_legacy_site_url(self):
        self.assertTrue(all(url.startswith('https://lustrid.ru/') for url in
                            self.locations(reverse('sitemap'), secure=True, HTTP_HOST='lustrid.ru')))
        self.assertTrue(all(url.startswith('http://localhost/') for url in
                            self.locations(reverse('sitemap_section', args=['products']), HTTP_HOST='localhost')))

    def test_unknown_sections_and_invalid_pages_return_404(self):
        for url in ['/sitemap-private.xml', '/sitemap-products.xml?p=999', '/sitemap-products.xml?p=bad']:
            self.assertEqual(self.client.get(url).status_code, 404)
