"""шаг 21: default furniture metadata and inherited SEO contracts."""
from types import SimpleNamespace
from html.parser import HTMLParser
from django.template.loader import render_to_string
from django.test import SimpleTestCase, RequestFactory


class HeadParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_head = False
        self.in_title = False
        self.title = ''
        self.meta = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.in_head = True
        if self.in_head and tag == 'title':
            self.in_title = True
        if self.in_head and tag == 'meta':
            self.meta.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'head':
            self.in_head = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


class FurnitureDefaultSeoTests(SimpleTestCase):
    def render_head(self, **context):
        request = RequestFactory().get('/example/', HTTP_HOST='localhost')
        return HeadParser(render_to_string('base.html', {'request': request, **context}))

    def test_default_head_describes_furniture(self):
        head = self.render_head()
        self.assertEqual(head.title.strip(), 'LUSTRID.RU — мебель на заказ')
        description = 'Мебель и столярные изделия на заказ для дома и бизнеса. Индивидуальные размеры, подбор материалов и сборка.'
        for meta in [{'name': 'description', 'content': description},
                     {'property': 'og:title', 'content': 'LUSTRID.RU — мебель на заказ'},
                     {'property': 'og:description', 'content': description},
                     {'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}]:
            self.assertIn(meta, head.meta)
        self.assertNotIn('автомоб', str(head.meta).lower())

    def test_custom_page_metadata_and_site_suffix_survive(self):
        page = SimpleNamespace(title='Страница', seo_title='Кухня & интерьер', search_description='Мебель "Дуб" & сборка')
        head = self.render_head(page=page, site=SimpleNamespace(site_name='Мастерская'))
        self.assertEqual(' '.join(head.title.split()), 'Кухня & интерьер – Мастерская')
        self.assertIn({'name': 'description', 'content': page.search_description}, head.meta)
        self.assertIn({'property': 'og:title', 'content': page.seo_title}, head.meta)
        self.assertIn({'property': 'og:description', 'content': page.search_description}, head.meta)

    def test_page_title_without_seo_title_is_preserved(self):
        head = self.render_head(page=SimpleNamespace(title='Материалы', seo_title='', search_description=''))
        self.assertEqual(head.title.strip(), 'Материалы')
        self.assertIn({'property': 'og:title', 'content': 'LUSTRID.RU — мебель на заказ'}, head.meta)
