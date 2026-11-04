"""шаг 52: remove duplicate selection, preserve existing links and home showcase."""
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product


class FurniturePortfolioTests(TestCase):
    def test_old_portfolio_address_redirects_to_home_section(self):
        for suffix in ['', '?page=2', '?next=https://example.test/']:
            self.assertRedirects(self.client.get(reverse('furniture_portfolio') + suffix),
                                 reverse('home') + '#portfolio', status_code=302)

    def test_navigation_and_home_showcase_return_to_existing_routes(self):
        product = Product.objects.create(title='Шкаф', slug='portfolio-case', price=100,
                                         image='products/original.jpg', is_featured=True)
        response = self.client.get('/')
        self.assertContains(response, 'id="portfolio"')
        self.assertContains(response, product.get_absolute_url())
        self.assertContains(response, product.image.url)
        self.assertContains(response, 'Весь каталог')
        self.assertNotContains(response, 'href="/portfolio/"')
        self.assertNotContains(response, 'furniture-portfolio.css')
        for name in ['catalog:catalog', 'furniture_services', 'furniture_materials',
                     'furniture_reviews', 'furniture_about', 'furniture_contacts']:
            response = self.client.get(reverse(name))
            self.assertContains(response, 'href="/#portfolio"', count=2)
            self.assertNotContains(response, 'href="/portfolio/"')
        product.refresh_from_db()
        self.assertTrue(product.is_featured)
        self.assertEqual(product.image.name, 'products/original.jpg')
        self.assertEqual(Product.objects.count(), 1)

    def test_empty_home_section_and_sitemap(self):
        self.assertContains(self.client.get('/'), 'id="portfolio"')
        self.assertNotContains(self.client.get('/sitemap-pages.xml'), '/portfolio/')
