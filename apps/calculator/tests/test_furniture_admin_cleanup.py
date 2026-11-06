"""Automotive calculator settings must not be exposed by the furniture admin."""
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.calculator.models import CalculatorDefinition, RateVersion
from datetime import date


class FurnitureCalculatorAdminTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser('calculator-cleanup-admin', 'admin@example.test', 'test-password')
        self.client.force_login(user)
        self.calculator = CalculatorDefinition.objects.create(slug='legacy-auto', title='Старый автомобильный расчёт')
        self.version = RateVersion.objects.create(calculator=self.calculator, name='Сохранённые ставки', effective_from=date(2026, 1, 1))

    def test_admin_index_has_no_calculator_group_and_product_admin_still_works(self):
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '/admin/calculator/')
        self.assertFalse(any(app['app_label'] == 'calculator' for app in response.context['app_list']))
        self.assertEqual(self.client.get(reverse('admin:products_product_changelist')).status_code, 200)
        self.assertEqual(self.client.get('/admin/calculator/').status_code, 404)

    def test_all_old_model_urls_are_disabled_including_direct_post(self):
        for model in apps.get_app_config('calculator').get_models():
            self.assertFalse(admin.site.is_registered(model), model.__name__)
            path = '/admin/calculator/' + model._meta.model_name + '/'
            for suffix in ['', 'add/', '1/change/', '1/delete/']:
                self.assertEqual(self.client.get(path + suffix).status_code, 404, path + suffix)
            self.assertEqual(self.client.post(path, {'action': 'delete_selected', '_selected_action': self.calculator.pk}).status_code, 404)

    def test_visiting_admin_does_not_delete_saved_calculator_data(self):
        before = list(CalculatorDefinition.objects.values()), list(RateVersion.objects.values())
        self.client.get(reverse('admin:index'))
        self.client.get('/admin/calculator/')
        self.assertEqual(before, (list(CalculatorDefinition.objects.values()), list(RateVersion.objects.values())))
        self.assertTrue(CalculatorDefinition.objects.filter(pk=self.calculator.pk).exists())
        self.assertTrue(RateVersion.objects.filter(pk=self.version.pk).exists())
