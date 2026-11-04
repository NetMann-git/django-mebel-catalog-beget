"""шаг 51: reuse existing featured selection without exposing hidden products."""
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product


class FurniturePortfolioTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='Шкаф <дуб>', slug='portfolio-oak', price=100,
                                             image='products/original-oak.jpg', is_featured=True)
        self.url = reverse('furniture_portfolio')

    def test_only_active_featured_products_and_original_photo(self):
        hidden = Product.objects.create(title='Секретное изделие', slug='portfolio-private', price=100,
                                        is_featured=True, is_active=False, image='products/private.jpg')
        ordinary = Product.objects.create(title='Не выбрано', slug='portfolio-ordinary', price=100)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['page_obj']), [self.product])
        for value in [hidden.title, hidden.image.name, ordinary.title]:
            self.assertNotContains(response, value)
        self.assertContains(response, self.product.image.url)
        self.assertContains(response, self.product.get_absolute_url())
        self.assertContains(response, 'Шкаф &lt;дуб&gt;')
        self.assertNotContains(response, '<h2>Шкаф <дуб>')
        self.assertNotContains(response, 'noindex')
        self.assertNotContains(response, 'themes/auto.css')
        self.assertEqual(Product.objects.count(), 3)

    def test_unselecting_is_immediately_reflected_and_no_fabricated_examples(self):
        self.product.is_featured = False
        self.product.save(update_fields=['is_featured'])
        response = self.client.get(self.url)
        self.assertContains(response, 'Подборка пока не заполнена')
        self.assertNotContains(response, self.product.image.name)
        self.assertNotContains(response, 'furniture-reference-01.jpg')

    def test_missing_photo_is_explicit(self):
        self.product.image = ''
        self.product.save(update_fields=['image'])
        self.assertContains(self.client.get(self.url), 'Фото пока нет')

    def test_all_selected_products_have_stable_pagination(self):
        products = [self.product] + [Product.objects.create(title=f'Мебель {i}', slug=f'portfolio-{i}',
                                    price=10, is_featured=True) for i in range(12)]
        first = self.client.get(self.url)
        second = self.client.get(self.url + '?page=2')
        self.assertEqual(list(first.context['page_obj']), list(reversed(products))[:12])
        self.assertEqual(list(second.context['page_obj']), [self.product])
        self.assertContains(first, '?page=2')
        self.assertContains(second, '?page=1')

    def test_home_navigation_and_sitemap(self):
        self.assertContains(self.client.get('/'), 'href="' + self.url + '"', count=3)
        self.assertContains(self.client.get('/'), 'id="portfolio"')
        self.assertContains(self.client.get('/sitemap-pages.xml'), self.url)
