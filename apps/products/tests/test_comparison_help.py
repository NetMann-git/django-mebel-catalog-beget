"""Шаг 62: понятные действия сравнения во всех режимах выдачи."""
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product


class ComparisonHelpTests(TestCase):
    def setUp(self):
        self.item = Product.objects.create(title='Шкаф <проверка>', slug='compare-help', price=100)

    def test_initial_and_selected_button_on_detail_and_ajax(self):
        for selected in (False, True):
            session = self.client.session
            session['comparison'] = [self.item.pk] if selected else []
            session.save()
            for url, headers in [
                (self.item.get_absolute_url(), {}),
                (reverse('catalog:catalog'), {}),
                (reverse('catalog:catalog'), {'HTTP_X_CATALOG_MODE': 'replace'}),
            ]:
                response = self.client.get(url, **headers)
                self.assertContains(response, 'Убрать из сравнения' if selected else 'Добавить к сравнению')
                self.assertContains(response, 'aria-pressed="true"' if selected else 'aria-pressed="false"')
                self.assertContains(response, 'fm-compare-icon')
                self.assertContains(response, 'Шкаф &lt;проверка&gt;')
                self.assertNotContains(response, 'data-product-title="Шкаф <проверка>"')

    def test_shared_help_assets_on_home_and_detail(self):
        for url in (reverse('home'), self.item.get_absolute_url()):
            response = self.client.get(url)
            self.assertContains(response, 'site-action-help.js', count=1)
            self.assertContains(response, 'site-action-help.css', count=1)
