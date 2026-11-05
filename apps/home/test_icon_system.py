"""Шаг 66: иконки соответствуют услугам и остаются рядом с заголовком."""
import re
from django.test import TestCase, SimpleTestCase
from django.template.loader import render_to_string
from apps.home.services_content import SERVICE_GROUPS
from apps.home.templatetags.furniture_icons import SERVICE_ICONS

class IconMappingTests(SimpleTestCase):
    def test_every_service_has_a_renderable_icon(self):
        titles={t for g in SERVICE_GROUPS for t,d in g['items']}
        self.assertEqual(titles,set(SERVICE_ICONS))
        self.assertGreaterEqual(len(set(SERVICE_ICONS.values())),15)
        for icon in set(SERVICE_ICONS.values())|{'heart','compare','phone','pin','wood','menu'}:
            s=render_to_string('home/includes/furniture_icon.html',{'icon':icon})
            self.assertIn('viewBox="0 0 24 24"',s)
            self.assertRegex(s,r'<(?:path|rect|circle|line|polyline|polygon|ellipse)\b')
            self.assertIn('aria-hidden="true"',s)

class IconPlacementTests(TestCase):
    def test_service_icons_are_inside_headings_not_standalone_badges(self):
        html=self.client.get('/services/').content.decode()
        cards=re.findall(r'<article class="fs-service">(.*?)</article>',html,re.S)
        self.assertEqual(len(cards),21)
        for c in cards:
            self.assertTrue(c.startswith('<h3 class="fi-card-heading"><svg'),c[:100])
            self.assertNotIn('class="fi-icon"',c)
        self.assertNotIn('fi-icon--small',html)

    def test_inline_favourites_and_comparison_do_not_use_emoji(self):
        from apps.products.models import Product
        p=Product.objects.create(title='Шкаф',slug='icon-buttons',price=100)
        r=self.client.get(p.get_absolute_url())
        self.assertContains(r,'fm-compare-icon')
        self.assertContains(r,'class="heart"><svg')
        self.assertNotContains(r,'❤️');self.assertNotContains(r,'🤍')

    def test_common_assets_and_mobile_menu_have_single_new_svg(self):
        for url in ['/','/about/','/services/','/materials/','/reviews/','/contacts/','/catalog/','/wishlist/']:
            html=self.client.get(url).content.decode()
            self.assertEqual(html.count('lustrid-icons.css'),1)
            self.assertNotIn('<span></span><span></span><span></span>',html)
