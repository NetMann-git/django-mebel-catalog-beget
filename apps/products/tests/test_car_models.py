"""Brand/model consistency, editor integration and manager permissions."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.products.car_model_forms import CarModelForm, ProductModelForm
from apps.products.forms import ProductForm
from apps.products.models import Brand, CarModel, Product


class CarModelTests(TestCase):
    """Exercise the same model/forms used by admin and manager."""

    @classmethod
    def setUpTestData(cls):
        cls.audi = Brand.objects.create(name='Audi', slug='audi')
        cls.bmw = Brand.objects.create(name='BMW', slug='bmw')
        cls.a3 = CarModel.objects.create(brand=cls.audi, name='A3', slug='a3')
        cls.manager = get_user_model().objects.create_user('manager', password='test')
        cls.manager.profile.role = 'manager'
        cls.manager.profile.save()

    def product_data(self, **extra) -> dict:
        data = {
            'title': 'Audi A3', 'slug': 'audi-a3', 'brand': self.audi.pk,
            'car_model': self.a3.pk, 'price': '1000000', 'currency': 'RUB',
            'availability_status': 'in_stock', 'rating': '0', 'reviews_count': '0',
        }
        data.update(extra)
        return data

    def test_both_product_forms_accept_matching_model(self):
        for form_class in (ProductForm, ProductModelForm):
            form = form_class(data=self.product_data())
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save(commit=False).car_model, self.a3)

    def test_both_forms_reject_wrong_brand(self):
        for form_class in (ProductForm, ProductModelForm):
            form = form_class(data=self.product_data(brand=self.bmw.pk))
            self.assertFalse(form.is_valid())
            self.assertIn('car_model', form.errors)

    def test_model_requires_brand(self):
        form = ProductForm(data=self.product_data(brand=''))
        self.assertFalse(form.is_valid())
        self.assertIn('car_model', form.errors)

    def test_old_product_can_remain_without_model(self):
        form = ProductForm(data=self.product_data(car_model=''))
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertIsNone(product.car_model_id)

    def test_nonexistent_model_rejected(self):
        form = ProductForm(data=self.product_data(car_model=99999))
        self.assertFalse(form.is_valid())
        self.assertIn('car_model', form.errors)

    def test_selector_has_brand_metadata_and_script(self):
        form = ProductForm()
        self.assertIn(f'data-brand="{self.audi.pk}"', str(form['car_model']))
        self.assertIn('car-model-select.js', str(form.media))

    def test_dictionary_latin_code_and_duplicate_validation(self):
        form = CarModelForm(data={
            'brand': self.audi.pk, 'name': 'Тест модель', 'slug': '', 'sort_order': 0,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().slug, 'test-model')
        duplicate = CarModelForm(data={
            'brand': self.audi.pk, 'name': 'a3', 'slug': '', 'sort_order': 0,
        })
        self.assertFalse(duplicate.is_valid())
        other = CarModelForm(data={
            'brand': self.bmw.pk, 'name': 'A3', 'slug': '', 'sort_order': 0,
        })
        self.assertTrue(other.is_valid(), other.errors)
        self.assertNotEqual(other.save().slug, self.a3.slug)

    def test_assigned_model_protected(self):
        Product.objects.create(title='Auto', slug='auto', price=1,
                               brand=self.audi, car_model=self.a3)
        with self.assertRaises(ProtectedError):
            self.a3.delete()
        self.a3.brand = self.bmw
        with self.assertRaises(ValidationError):
            self.a3.full_clean()

    def test_guests_and_customers_cannot_create_models(self):
        url = reverse('catalog:car_model_create')
        data = {'brand': self.audi.pk, 'name': 'A4', 'slug': '', 'sort_order': 0}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        customer = get_user_model().objects.create_user('customer')
        self.client.force_login(customer)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertFalse(CarModel.objects.filter(name='A4').exists())

    def test_manager_create_edit_and_delete(self):
        self.client.force_login(self.manager)
        data = {'brand': self.audi.pk, 'name': 'A4', 'slug': '', 'sort_order': 0}
        response = self.client.post(reverse('catalog:car_model_create'), data)
        self.assertRedirects(response, reverse('catalog:car_model_list'), fetch_redirect_response=False)
        model = CarModel.objects.get(name='A4')
        data.update(name='A5', slug=model.slug)
        response = self.client.post(reverse('catalog:car_model_edit', args=[model.pk]), data)
        self.assertEqual(response.status_code, 302)
        model.refresh_from_db()
        self.assertEqual(model.name, 'A5')
        self.client.post(reverse('catalog:car_model_delete', args=[model.pk]))
        self.assertFalse(CarModel.objects.filter(pk=model.pk).exists())

    def test_manager_pages_render_and_get_does_not_delete(self):
        self.client.force_login(self.manager)
        for name, args in (
            ('car_model_list', []), ('car_model_create', []),
            ('car_model_edit', [self.a3.pk]), ('car_model_delete', [self.a3.pk]),
        ):
            response = self.client.get(reverse('catalog:' + name, args=args))
            self.assertEqual(response.status_code, 200)
        self.assertTrue(CarModel.objects.filter(pk=self.a3.pk).exists())

    def test_manager_cannot_delete_assigned_model(self):
        Product.objects.create(title='Auto', slug='auto', price=1,
                               brand=self.audi, car_model=self.a3)
        self.client.force_login(self.manager)
        self.client.post(reverse('catalog:car_model_delete', args=[self.a3.pk]))
        self.assertTrue(CarModel.objects.filter(pk=self.a3.pk).exists())

    def test_brand_with_models_is_not_deleted_by_manager(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('catalog:brand_delete', args=[self.audi.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Brand.objects.filter(pk=self.audi.pk).exists())

    def test_furniture_admin_does_not_expose_vehicle_selector(self):
        user = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'test',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('admin:products_product_add'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-car-model-select')
        self.assertNotContains(response, 'car-model-select.js')
