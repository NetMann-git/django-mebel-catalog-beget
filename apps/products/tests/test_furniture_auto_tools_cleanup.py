"""Car-only tools are unavailable; saved legacy relations remain intact."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from apps.products.models import Brand, CarModel, EquipmentGroup, EquipmentOption, Product, VehicleImportSource


class FurnitureAutoToolsCleanupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('auto-tools-admin', 'admin@example.test', 'test-password')
        self.user.profile.role = 'manager'
        self.user.profile.save()
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name='Мастерская', slug='workshop')
        self.car = CarModel.objects.create(name='Старая модель', slug='legacy-car', brand=self.brand)
        self.product = Product.objects.create(title='Изделие', slug='legacy-item', price=100, brand=self.brand, car_model=self.car)
        self.source = VehicleImportSource.objects.create(product=self.product, listing_id='12345',
            source_url='https://example.test/legacy', raw_json={'preserve': True})
        self.group = EquipmentGroup.objects.create(name='Особенности', slug='features')
        self.option = EquipmentOption.objects.create(name='Подсветка', group=self.group, encar_standard_code='010')
        self.product.equipment.add(self.option)

    def test_manager_tools_and_direct_endpoints_are_removed(self):
        response = self.client.get(reverse('users:manager_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Импорт из Encar')
        self.assertNotContains(response, 'Модели автомобилей')
        for path in ['/catalog/manage/import-encar/', '/catalog/manage/import-encar/photo/token/0/',
                     '/catalog/manage/car-models/', '/catalog/manage/car-models/create/',
                     '/catalog/manage/car-models/1/edit/', '/catalog/manage/car-models/1/delete/']:
            self.assertEqual(self.client.get(path).status_code, 404, path)
            self.assertEqual(self.client.post(path, {'action': 'confirm'}).status_code, 404, path)
        for name in ['catalog:import_encar','catalog:car_model_list','catalog:car_model_create']:
            with self.assertRaises(NoReverseMatch):
                reverse(name)

    def test_admin_registry_and_old_model_urls_are_disabled(self):
        index = self.client.get(reverse('admin:index'))
        self.assertEqual(index.status_code, 200)
        for model in [CarModel, VehicleImportSource]:
            self.assertFalse(admin.site.is_registered(model))
            prefix = '/admin/products/' + model._meta.model_name + '/'
            self.assertNotContains(index, prefix)
            for suffix in ['', 'add/', '1/change/', '1/delete/']:
                self.assertEqual(self.client.get(prefix + suffix).status_code, 404)
        self.assertTrue(admin.site.is_registered(Product))
        self.assertTrue(admin.site.is_registered(EquipmentOption))

    def test_generic_option_editor_hides_source_code_and_preserves_it_on_post(self):
        url = reverse('admin:products_equipmentoption_change', args=[self.option.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="encar_standard_code"')
        self.assertNotContains(response, 'Код Encar')
        response = self.client.post(url, {'name':'Подсветка полок', 'group':self.group.pk,
            'sort_order':'2', 'is_active':'on', 'encar_standard_code':'999', '_save':'Сохранить'})
        self.assertEqual(response.status_code, 302)
        self.option.refresh_from_db()
        self.assertEqual(self.option.name, 'Подсветка полок')
        self.assertEqual(self.option.encar_standard_code, '010')
        self.assertTrue(self.product.equipment.filter(pk=self.option.pk).exists())

    def test_existing_records_and_product_editors_are_preserved(self):
        before = list(CarModel.objects.values()), list(VehicleImportSource.objects.values()), list(Product.objects.values())
        for url in [reverse('catalog:product_edit', args=[self.product.pk]),
                    reverse('admin:products_product_change', args=[self.product.pk]), '/catalog/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'name="car_model"')
        after = list(CarModel.objects.values()), list(VehicleImportSource.objects.values()), list(Product.objects.values())
        self.assertEqual(before, after)
        self.assertTrue(self.product.equipment.filter(pk=self.option.pk).exists())
