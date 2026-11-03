"""Furniture attribute pages preserve the shared dictionary and editor contract."""
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from apps.products.models import AttributeType, AttributeValue, Product, ProductAttribute


class FurnitureAttributePagesTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser('workshop', password='test-only')
        self.client.force_login(user)
        self.kind = AttributeType.objects.create(name='Материал', slug='material', data_type='choice')
        self.value = AttributeValue.objects.create(attribute_type=self.kind, value='Дуб')
        self.product = Product.objects.create(title='Стол', slug='table', price=100)
        self.row = ProductAttribute.objects.create(product=self.product, attribute_type=self.kind, attribute_value=self.value)

    def test_all_pages_render_furniture_shell_without_changing_data(self):
        routes = [('attribute_type_list_manage', []), ('attribute_type_create', []),
                  ('attribute_type_edit', [self.kind.pk]), ('attribute_value_edit', [self.kind.pk, self.value.pk]),
                  ('attribute_type_delete', [self.kind.pk]), ('attribute_value_delete', [self.kind.pk, self.value.pk]),
                  ('product_attributes', [self.product.pk])]
        for name, args in routes:
            with self.subTest(name=name):
                response = self.client.get(reverse('catalog:' + name, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'furniture-attributes.css')
                self.assertContains(response, 'noindex, nofollow')
                self.assertNotContains(response, 'автомобил')
        self.assertEqual(ProductAttribute.objects.get().pk, self.row.pk)
        self.assertEqual(AttributeValue.objects.get().value, 'Дуб')

    def test_invalid_value_keeps_bound_errors_and_existing_values(self):
        response = self.client.post(reverse('catalog:attribute_value_create', args=[self.kind.pk]), {'value': 'Дуб', 'sort_order': '0'})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context['value_form'].errors)
        self.assertContains(response, 'Значения характеристики', status_code=400)
        self.assertEqual(AttributeValue.objects.count(), 1)

    def test_shared_value_edit_keeps_product_links(self):
        other = Product.objects.create(title='Полка', slug='shelf', price=50)
        ProductAttribute.objects.create(product=other, attribute_type=self.kind, attribute_value=self.value)
        response = self.client.post(reverse('catalog:attribute_value_edit', args=[self.kind.pk, self.value.pk]), {'value': 'Дуб натуральный', 'sort_order': 2})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductAttribute.objects.filter(attribute_value_id=self.value.pk).count(), 2)
        self.row.refresh_from_db()
        self.assertEqual(self.row.attribute_value.value, 'Дуб натуральный')

    def test_editor_contract_and_csrf(self):
        url = reverse('catalog:product_attributes', args=[self.product.pk])
        response = self.client.get(url)
        for hook in ['attribute-editor-add', 'attribute-editor-rows', 'attribute-editor-empty', 'id_attributes-TOTAL_FORMS', 'data-product-attribute-row', 'product-attribute-inputs.js']:
            self.assertContains(response, hook)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(get_user_model().objects.get(username='workshop'))
        self.assertEqual(strict.post(url, {}).status_code, 403)
        self.assertEqual(ProductAttribute.objects.count(), 1)
