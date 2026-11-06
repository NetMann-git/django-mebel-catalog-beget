"""Furniture labels and existing callback links in Django admin."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Product
from .models import CallbackRequest


class FurnitureCallbackAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser(
            'callback-admin', 'admin@example.test', 'test-password'))
        self.product = Product.objects.create(title='Шкаф для прихожей', slug='admin-wardrobe', price=100)
        self.item = CallbackRequest.objects.create(
            name='Анна', phone='+79990000000', product=self.product, source='product_order')
        self.url = reverse('admin:appointments_callbackrequest_change', args=[self.item.pk])

    def test_list_and_readonly_product_have_furniture_labels(self):
        self.assertEqual(CallbackRequest._meta.get_field('product').verbose_name, 'Изделие')
        for url in [self.url, reverse('admin:appointments_callbackrequest_changelist')]:
            response = self.client.get(url)
            self.assertContains(response, 'Изделие')
            self.assertContains(response, self.product.title)
            self.assertNotContains(response, 'Автомобиль')
        self.assertContains(self.client.get(self.url), 'Изделие и источник')

    def test_status_edit_preserves_original_product_and_source(self):
        response = self.client.post(self.url, {
            'name': 'Анна', 'phone': self.item.phone, 'email': '', 'city': '',
            'comment': 'Уточнены размеры', 'status': 'processed', 'product': '', 'source': 'forged', '_save': 'Сохранить'})
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'processed')
        self.assertEqual(self.item.product_id, self.product.pk)
        self.assertEqual(self.item.source, 'product_order')
