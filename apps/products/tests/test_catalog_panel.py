"""Шаг 68: раскрытая разметка и ограниченный индикатор поворота."""
import re
from pathlib import Path
from django.test import TestCase, SimpleTestCase
from django.contrib.staticfiles import finders

class CatalogPanelTests(TestCase):
    def test_full_and_ajax_responses_start_with_open_panel(self):
        for headers in ({},{'HTTP_X_CATALOG_MODE':'replace'}):
            html=self.client.get('/catalog/',**headers).content.decode()
            self.assertIn('<details id="catalog-filter-panel" open>',html)
            self.assertIn('class="fc-filter-toggle-icon" aria-hidden="true">+</span>',html)
            self.assertIn('class="fm-filter-title"',html)
            self.assertIn('Подобрать мебель</span>',html)

class CatalogIndicatorTests(SimpleTestCase):
    def test_rotation_selectors_only_target_the_disclosure_indicator(self):
        css=Path(finders.find('products/css/furniture-catalog.css')).read_text()
        rules=re.findall(r'([^{}]+)\{([^{}]+)\}',css)
        rotation=[selector for selector,body in rules if 'summary' in selector and 'rotate(' in body]
        self.assertTrue(rotation)
        self.assertTrue(all('>.fc-filter-toggle-icon' in selector for selector in rotation))
        self.assertNotIn('.fc-sidebar summary span{',css)
