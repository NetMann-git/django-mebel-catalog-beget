"""Шаг 67: служебные SVG сохраняют семантику управляющих элементов."""
from html.parser import HTMLParser
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

class Buttons(HTMLParser):
    def __init__(self):super().__init__();self.buttons=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='button':self.current={'attrs':dict(attrs),'svg':False};self.buttons.append(self.current)
        if tag=='svg' and self.current is not None:self.current['svg']=True
    def handle_endtag(self,tag):
        if tag=='button':self.current=None

class InterfaceIconsTests(TestCase):
    def test_gallery_controls_keep_accessible_labels(self):
        html=render_to_string('products/includes/furniture_lightbox.html',{'box_id':'test','label':'Фото'})
        parser=Buttons();parser.feed(html)
        self.assertEqual(len(parser.buttons),3)
        self.assertTrue(all(b['svg'] and b['attrs'].get('aria-label') and b['attrs']['type']=='button' for b in parser.buttons))
        self.assertIn('fm-ui-back',html)

    def test_catalog_normal_and_ajax_keep_chip_links(self):
        url='/catalog/?q=oak'
        for headers in [{},{'HTTP_X_CATALOG_MODE':'replace'}]:
            r=self.client.get(url,**headers);self.assertEqual(r.status_code,200)
            self.assertContains(r,'class="filter-chip"')
            self.assertNotContains(r,'aria-hidden="true">×</span>')
            self.assertContains(r,'name="q"')
            self.assertContains(r,'fm-filter-title')

    def test_account_icons_preserve_counters_and_post_logout(self):
        user=get_user_model().objects.create_user('icon-account');self.client.force_login(user)
        html=self.client.get('/account/dashboard/').content.decode()
        self.assertEqual(html.count('class="fd-stat-title"'),3)
        self.assertIn('method="post" action="/account/logout/"',html)
        self.assertIn('csrfmiddlewaretoken',html)
        self.assertIn('data-smart-search-input',html)

    def test_search_button_has_search_icon_and_text(self):
        r=self.client.get('/search/?query=oak')
        self.assertContains(r,'fm-ui-icon')
        self.assertContains(r,'Найти</button>')
