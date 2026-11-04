"""шаг 46: материалы доступны посетителю через существующую оболочку сайта."""
from django.test import TestCase
from django.urls import reverse


class FurnitureMaterialsTests(TestCase):
    def test_anonymous_page_has_materials_and_existing_request_path(self):
        response = self.client.get(reverse('furniture_materials'))
        self.assertEqual(response.status_code, 200)
        for text in ['ЛДСП и МДФ', 'Натуральный массив дерева', 'Фурнитура',
                     'Внешний вид и бюджет', 'С чего начать подбор']:
            self.assertContains(response, text)
        self.assertContains(response, 'href="' + reverse('home') + '#callback"')
        self.assertContains(response, 'href="' + reverse('furniture_services') + '"')
        self.assertNotContains(response, 'noindex')
        self.assertNotContains(response, 'themes/auto.css')

    def test_navigation_home_anchor_and_sitemap(self):
        target = reverse('furniture_materials')
        for url in [reverse('home'), reverse('catalog:catalog'), reverse('furniture_services')]:
            response = self.client.get(url)
            self.assertContains(response, 'href="' + target + '"', count=3 if url == '/' else 2)
        self.assertContains(self.client.get('/'), 'id="materials"')
        self.assertContains(self.client.get('/sitemap-pages.xml'), target)
