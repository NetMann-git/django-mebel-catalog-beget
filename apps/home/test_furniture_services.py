"""шаг 45: public services page uses supplied content and existing request path."""
from django.test import TestCase
from django.urls import reverse,resolve
from apps.home.services_content import SERVICE_GROUPS


class FurnitureServicesTests(TestCase):
    def test_public_page_has_all_five_sections_and_twenty_one_services(self):
        response=self.client.get(reverse('furniture_services'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(sum(len(g['items']) for g in SERVICE_GROUPS),21)
        for group in SERVICE_GROUPS:
            self.assertContains(response,'id="'+group['id']+'"')
            self.assertContains(response,'href="#'+group['id']+'"')
            for title,_ in group['items']:self.assertContains(response,title)
        self.assertContains(response,reverse('home')+'#callback')
        self.assertContains(response,reverse('catalog:catalog'))
        self.assertContains(response,'furniture-services.css')
        self.assertNotContains(response,'themes/auto.css')
        self.assertNotContains(response,'noindex')

    def test_navigation_links_and_sitemap_include_the_public_page(self):
        target=reverse('furniture_services')
        self.assertEqual(resolve(target).url_name,'furniture_services')
        for url in [reverse('home'),reverse('catalog:catalog')]:
            self.assertContains(self.client.get(url),'href="'+target+'"',count=2)
        response=self.client.get('/sitemap-pages.xml')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,target)
