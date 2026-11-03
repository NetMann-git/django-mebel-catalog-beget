"""Furniture editor boundaries and preservation of hidden legacy fields."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.products.furniture_forms import FurnitureAdminForm, FurnitureProductForm
from apps.products.models import Brand, CarModel, Product, EquipmentGroup, EquipmentOption


class FurnitureFormTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name='Мастерская', slug='workshop')
        self.other_brand = Brand.objects.create(name='Другая', slug='other-workshop')
        self.car = CarModel.objects.create(brand=self.brand, name='Старая модель', slug='legacy')
        self.group = EquipmentGroup.objects.create(name='Фурнитура', slug='fittings')
        self.option = EquipmentOption.objects.create(group=self.group, name='Доводчики', encar_standard_code='010')
        self.inactive = EquipmentOption.objects.create(group=self.group, name='Старая опция', is_active=False)
        self.user = get_user_model().objects.create_superuser('editor', password='test-only')
        self.client.force_login(self.user)

    def data(self, **extra):
        return {'title': 'Шкаф', 'price': '12345', 'currency': 'RUB',
                'availability_status': 'in_stock', 'brand': self.brand.pk,
                'rating': '0', 'reviews_count': '0', **extra}

    def test_new_product_ignores_forged_car_model_and_accepts_type_text(self):
        form = FurnitureProductForm(data=self.data(car_model=self.car.pk, product_type='Встроенный шкаф'))
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertIsNone(product.car_model_id)
        self.assertEqual(product.product_type, 'Встроенный шкаф')
        self.assertTrue(product.slug.isascii())
        self.assertIn('type="text"', str(form['product_type']))

    def test_hidden_model_and_linked_brand_preserved_in_both_forms(self):
        product = Product.objects.create(title='Старое изделие', slug='keep-url', price=7,
                                         brand=self.brand, car_model=self.car, product_type='Прежний тип')
        for cls in (FurnitureProductForm, FurnitureAdminForm):
            product.refresh_from_db()
            form = cls(instance=product, data=self.data(brand=self.other_brand.pk, car_model='99999',
                        product_type='Прежний тип', slug='forged-url'))
            self.assertNotIn('car_model', form.fields)
            self.assertTrue(form.fields['brand'].disabled)
            self.assertTrue(form.is_valid(), form.errors)
            saved = form.save()
            self.assertEqual(saved.car_model_id, self.car.pk)
            self.assertEqual(saved.brand_id, self.brand.pk)
            self.assertEqual(saved.slug, 'keep-url')

    def test_grouped_options_no_source_code_and_existing_inactive_preserved(self):
        product = Product.objects.create(title='Шкаф', slug='options', price=1)
        product.equipment.add(self.inactive)
        form = FurnitureProductForm(instance=product)
        self.assertIn('equipment.css', str(form.media))
        self.assertNotIn('car-model-select.js', str(form.media))
        html = str(form['equipment'])
        self.assertIn('Фурнитура', html)
        self.assertIn('Доводчики', html)
        self.assertIn('отключена', html)
        self.assertNotIn('[код', html)
        self.assertNotIn('[без кода]', html)
        self.assertIn('form="product-form"', html)
        form = FurnitureProductForm(instance=product, data=self.data(equipment=[self.inactive.pk]))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(list(form.save().equipment.all()), [self.inactive])

    def test_pages_form_fields_and_gallery_preserved(self):
        product = Product.objects.create(title='Шкаф', slug='pages', price=1)
        for url in (reverse('catalog:product_create'),
                    reverse('catalog:product_edit', args=[product.pk]),
                    reverse('admin:products_product_add'),
                    reverse('admin:products_product_change', args=[product.pk])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'id="id_car_model"')
            self.assertNotContains(response, 'car-model-select.js')
            self.assertContains(response, 'Название изделия')
        response = self.client.get(reverse('catalog:product_edit', args=[product.pk]))
        self.assertContains(response, 'id="product-gallery"')
        self.assertNotContains(response, 'Справочник моделей автомобилей')

    def test_manager_create_edit_and_validation_without_javascript(self):
        create = reverse('catalog:product_create')
        response = self.client.post(create, self.data(price=''))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.exists())
        response = self.client.post(create, self.data(product_type='Мебель из массива'))
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get()
        response = self.client.post(reverse('catalog:product_edit', args=[product.pk]),
            self.data(title='Шкаф изменён', slug='unexpected', equipment=[self.option.pk],
                      product_type='Мебель из массива'))
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.title, 'Шкаф изменён')
        self.assertNotEqual(product.slug, 'unexpected')
        self.assertEqual(list(product.equipment.all()), [self.option])

    def test_anonymous_and_unprivileged_do_not_get_editor(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('catalog:product_create')).status_code, 302)
        user = get_user_model().objects.create_user('customer')
        self.client.force_login(user)
        self.assertEqual(self.client.post(reverse('catalog:product_create'), self.data()).status_code, 302)
        self.assertFalse(Product.objects.exists())
