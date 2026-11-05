"""Шаг 69: документы мебельного сайта без бренда и реквизитов другого проекта."""
import re
from django.test import TestCase
from django.urls import reverse

class FurnitureLegalPagesTests(TestCase):
    urls = ('public_offer','privacy_policy','personal_data_consent')

    def test_documents_use_furniture_shell_and_no_foreign_identity(self):
        for name in self.urls:
            with self.subTest(name=name):
                r=self.client.get(reverse(name));self.assertEqual(r.status_code,200)
                html=r.content.decode()
                for foreign in ['carstar-rnd.ru','Подберем АВТО','автомоб','Аксюк','232201980333']:
                    self.assertNotIn(foreign,html)
                self.assertIn('home/branding/logo-compact-dark.svg',html)
                self.assertIn('home/branding/logo-full-light.svg',html)
                self.assertEqual(len(re.findall(r'<main\b',html)),1)
                self.assertEqual(r['X-Robots-Tag'],'noindex, follow')
                self.assertIn('<meta name="robots" content="noindex, follow">',html)
                self.assertIn('Реквизиты оператора LUSTRID.RU уточняются.',html)

    def test_document_navigation_points_to_working_pages(self):
        for name in self.urls:
            html=self.client.get(reverse(name)).content.decode()
            for path in ['/terms/','/privacy/','/consent/','/contacts/']:
                self.assertIn('href="'+path+'"',html)
                self.assertEqual(self.client.get(path).status_code,200)

    def test_existing_draft_status_and_safe_methods_preserved(self):
        for name in self.urls:
            url=reverse(name)
            self.assertEqual(self.client.head(url).status_code,200)
            self.assertEqual(self.client.post(url,{}).status_code,405)
        self.assertContains(self.client.get('/privacy/'),'Проект для согласования')
        self.assertContains(self.client.get('/consent/'),'Проект отдельного согласия')
        terms=self.client.get('/terms/')
        self.assertContains(terms,'нет утверждённой публичной оферты')
        self.assertContains(terms,'Условия заказа мебели')

    def test_home_footer_links_documents_and_real_inquiry_fields_are_described(self):
        html=self.client.get('/').content.decode()
        for path in ['/terms/','/privacy/','/consent/']:
            self.assertIn('href="'+path+'"',html)
        policy=self.client.get('/privacy/')
        for text in ['Запрос по изделию','город / населённый пункт','email','комментарий','выбранное изделие']:
            self.assertContains(policy,text)
