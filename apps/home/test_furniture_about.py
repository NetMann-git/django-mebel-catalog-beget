"""шаг 49: workshop information and existing public navigation."""
from django.test import TestCase
from django.urls import reverse


class FurnitureAboutTests(TestCase):
    def test_anonymous_workshop_page_and_existing_links(self):
        response = self.client.get(reverse('furniture_about'))
        self.assertEqual(response.status_code, 200)
        for text in ['Мебель, созданная под конкретное пространство',
                     'Индивидуальное проектирование', 'Для частных клиентов',
                     'Для коммерческих заказчиков', 'Сборка и подгонка на объекте']:
            self.assertContains(response, text)
        for name in ['furniture_services', 'furniture_materials', 'catalog:catalog']:
            self.assertContains(response, 'href="' + reverse(name) + '"')
        self.assertContains(response, 'href="' + reverse('home') + '#callback"')
        self.assertNotContains(response, 'noindex')
        self.assertNotContains(response, 'themes/auto.css')
        self.assertNotContains(response, 'автомобиль')

    def test_home_footer_and_sitemap_links(self):
        target = reverse('furniture_about')
        response = self.client.get('/')
        self.assertContains(response, 'href="' + target + '"', count=2)
        self.assertContains(response, 'id="advantages"')
        for name in ['catalog:catalog', 'furniture_services', 'furniture_materials', 'furniture_reviews']:
            self.assertContains(self.client.get(reverse(name)), 'href="' + target + '"', count=1)
        self.assertContains(self.client.get('/sitemap-pages.xml'), target)
