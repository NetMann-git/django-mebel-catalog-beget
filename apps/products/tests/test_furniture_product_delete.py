from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from apps.products.models import Product


class FurnitureProductDeleteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('delete-manager')
        self.user.profile.role = 'manager'; self.user.profile.save()
        self.client.force_login(self.user)
        self.product = Product.objects.create(title='Шкаф <script>не код</script>', slug='delete-wardrobe', price=100)
        self.url = reverse('catalog:product_delete', args=[self.product.pk])

    def test_confirmation_uses_furniture_shell_and_does_not_delete_on_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home/furniture_base.html')
        self.assertContains(response, 'Удалить изделие?')
        self.assertContains(response, 'furniture-categories.css')
        self.assertNotContains(response, 'products/css/manage.css')
        self.assertNotContains(response, 'themes/auto.css')
        self.assertContains(response, 'Шкаф &lt;script&gt;не код&lt;/script&gt;')
        self.assertContains(response, reverse('catalog:product_edit', args=[self.product.pk]))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_confirmed_post_deletes_and_returns_to_list(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('catalog:product_list_manage'), fetch_redirect_response=False)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_customer_cannot_delete_and_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(self.url).status_code, 403)
        customer = get_user_model().objects.create_user('delete-customer')
        self.client.force_login(customer)
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
