"""шаг 43: shared published contacts, no hidden content rules or private values."""
from django.test import TestCase, RequestFactory
from django.urls import reverse
from apps.home.models import ContactSettings
from apps.home.templatetags.furniture_contacts import furniture_contacts


class FurnitureContactTests(TestCase):
    def setUp(self):
        self.record,_=ContactSettings.objects.update_or_create(pk=1,defaults={
            'phone_primary':'+7 (900) 111-22-33','phone_secondary':'+7 (900) 444-55-66',
            'address':'Мастерская <дуб>','map_url':'https://maps.example.test/workshop',
            'telegram_url':'https://t.me/workshop_test','vk_url':'https://vk.com/workshop_test',
            'max_url':'https://max.example.test/workshop','is_published':True})

    def test_shared_home_and_catalog_show_published_contacts_and_safe_links(self):
        for url in [reverse('home'), reverse('catalog:catalog'), reverse('users:login')]:
            response=self.client.get(url)
            for text in ['tel:+79001112233','tel:+79004445566','Мастерская &lt;дуб&gt;',
                         self.record.telegram_url,self.record.vk_url,self.record.max_url,
                         self.record.map_url,'noopener noreferrer','furniture-contacts.css']:
                self.assertContains(response,text)
            self.assertNotContains(response,'Мастерская <дуб>')
        self.record.refresh_from_db();self.assertEqual(self.record.phone_primary,'+7 (900) 111-22-33')

    def test_unpublished_or_absent_record_never_exposes_contacts(self):
        self.record.is_published=False;self.record.save(update_fields=['is_published'])
        for url in [reverse('home'),reverse('catalog:catalog')]:
            response=self.client.get(url)
            for text in [self.record.phone_primary,self.record.address,self.record.telegram_url,'Контакты мастерской']:
                self.assertNotContains(response,text)
        self.record.delete()
        self.assertEqual(self.client.get(reverse('home')).status_code,200)

    def test_published_settings_are_shown_even_if_they_match_initial_values(self):
        # Publication in the existing editor is authoritative; no content blacklist.
        from importlib import import_module
        module = import_module('apps.home.migrations.0008_seed_contacts')
        class HistoricalApps:
            def get_model(self, app_label, model_name):
                return ContactSettings
        module.seed_contacts(HistoricalApps(), None)
        self.record.refresh_from_db()
        response=self.client.get(reverse('home'))
        for text in [self.record.phone_primary,self.record.phone_secondary,self.record.address,
                     self.record.telegram_url,self.record.vk_url,self.record.max_url,self.record.map_url]:
            from django.utils.html import escape
            self.assertContains(response,escape(text))
        self.assertContains(response,'Контакты мастерской')
        self.assertContains(response,'tel:+79885808899')

    def test_map_only_published_record_is_not_suppressed(self):
        ContactSettings.objects.filter(pk=1).update(phone_primary='',phone_secondary='',address='',telegram_url='',vk_url='',max_url='')
        response=self.client.get(reverse('home'))
        self.assertContains(response,self.record.map_url)
        self.assertContains(response,'Контакты мастерской')

    def test_unsafe_links_are_not_rendered(self):
        ContactSettings.objects.filter(pk=1).update(telegram_url='javascript:alert(1)',vk_url='data:text/html,test',max_url='https://user:secret@example.test/',map_url='//example.test/map')
        response=self.client.get(reverse('home'))
        for text in ['javascript:alert','data:text/html','user:secret','//example.test/map']:
            self.assertNotContains(response,text)
        self.assertContains(response,'tel:+79001112233')

    def test_template_tag_reuses_one_query_per_request(self):
        context={'request':RequestFactory().get('/')}
        with self.assertNumQueries(1):
            first=furniture_contacts(context);second=furniture_contacts(context)
        self.assertEqual(first,second)
