"""Clothing size admin and automotive client labels are absent from furniture UI."""
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.home.models import ClientShowcase
from apps.size_helper.models import SizeTable, SizeRecommendation


class FurnitureLegacyLabelsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser('legacy-label-admin', 'admin@example.test', 'test-password')
        user.profile.role = 'manager'
        user.profile.save()
        self.client.force_login(user)
        self.record = ClientShowcase.objects.create(name='Клиент', vehicle='BMW X5', legacy_image='legacy/client.jpg')
        self.size = SizeTable.objects.create(size='48', chest=96, waist=80, hips=100, height_min=170, height_max=180)
        self.recommendation = SizeRecommendation.objects.create(size='48', height_min=170, height_max=180,
            bust_min=90, bust_max=100, waist_min=75, waist_max=85, hips_min=95, hips_max=105)

    def test_clothing_size_models_and_direct_admin_pages_are_disabled(self):
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '/admin/size_helper/')
        self.assertEqual(self.client.get('/admin/size_helper/').status_code, 404)
        for model in apps.get_app_config('size_helper').get_models():
            self.assertFalse(admin.site.is_registered(model))
            root = '/admin/size_helper/' + model._meta.model_name + '/'
            for suffix in ['', 'add/', '1/change/', '1/delete/']:
                self.assertEqual(self.client.get(root + suffix).status_code, 404)
            self.assertEqual(self.client.post(root, {'action':'delete_selected'}).status_code, 404)
        self.assertTrue(SizeTable.objects.filter(pk=self.size.pk).exists())
        self.assertTrue(SizeRecommendation.objects.filter(pk=self.recommendation.pk).exists())

    def test_client_manager_and_admin_use_project_labels_without_changing_saved_values(self):
        before = list(ClientShowcase.objects.values())
        urls = [reverse('home:client_create'), reverse('home:client_edit',args=[self.record.pk]),
                reverse('admin:home_clientshowcase_add'), reverse('admin:home_clientshowcase_change', args=[self.record.pk])]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Изделие или проект')
            self.assertNotContains(response, '>Автомобиль<')
            self.assertNotContains(response, 'KIA Sorento')
        index = self.client.get(reverse('home:client_list_manage'))
        self.assertContains(index, 'Имя клиента или проект')
        self.assertContains(index, 'BMW X5')
        self.assertNotContains(index, 'Имя клиента или автомобиль')
        response = self.client.get(reverse('admin:home_clientshowcase_changelist'))
        self.assertContains(response, 'Изделие или проект')
        self.assertEqual(before, list(ClientShowcase.objects.values()))

    def test_project_edit_keeps_other_existing_fields_and_searches_project(self):
        response = self.client.post(reverse('home:client_edit', args=[self.record.pk]), {
            'name':'Клиент', 'vehicle':'Кухня для квартиры', 'rutube_url':'', 'sort_order':'5', 'is_published':'on'})
        self.assertEqual(response.status_code, 302)
        self.record.refresh_from_db()
        self.assertEqual(self.record.vehicle, 'Кухня для квартиры')
        self.assertEqual(self.record.legacy_image, 'legacy/client.jpg')
        self.assertTrue(self.record.is_published)
        response = self.client.get(reverse('home:client_list_manage'), {'search':'Кухня'})
        self.assertContains(response, 'Кухня для квартиры')
        self.assertEqual(len(response.context['clients']), 1)

    def test_admin_project_edit_and_original_data_schema_stay_compatible(self):
        response = self.client.post(reverse('admin:home_clientshowcase_change', args=[self.record.pk]), {
            'name':'Клиент', 'vehicle':'Шкаф в прихожую', 'rutube_url':'', 'sort_order':'3', 'is_published':'on', '_save':'Сохранить'})
        self.assertEqual(response.status_code, 302)
        self.record.refresh_from_db()
        self.assertEqual(self.record.vehicle, 'Шкаф в прихожую')
        self.assertEqual(self.record.legacy_image, 'legacy/client.jpg')
