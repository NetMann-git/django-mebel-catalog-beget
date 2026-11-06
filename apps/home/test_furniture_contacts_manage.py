"""Furniture shell and unchanged contact editing workflow."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import ContactSettings


class FurnitureContactsManageTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('contacts-editor')
        user.profile.role = 'manager'
        user.profile.save()
        self.client.force_login(user)
        self.url = reverse('home:contacts_manage')
        self.item, _ = ContactSettings.objects.update_or_create(pk=1, defaults={
            'phone_primary': '+79001112233', 'address': 'Адрес мастерской',
            'map_url': 'https://yandex.ru/map-widget/v1/?z=12', 'is_published': True})

    def test_furniture_shell_navigation_and_saved_values(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'home/furniture_base.html')
        self.assertContains(response, 'Контакты мастерской')
        self.assertContains(response, reverse('users:manager_dashboard'))
        self.assertContains(response, 'home/css/furniture-contacts-manage.css')
        self.assertContains(response, self.item.phone_primary)
        self.assertNotContains(response, 'home/css/client-manage.css')
        self.assertNotContains(response, 'themes/auto.css')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'noindex, nofollow')

    def test_save_and_invalid_form_keep_data_and_new_shell(self):
        data = {'phone_primary': '+79002223344', 'phone_secondary': '', 'address': 'Новый адрес',
                'map_url': self.item.map_url, 'telegram_url': '', 'vk_url': '', 'max_url': '', 'is_published': 'on'}
        response = self.client.post(self.url, data)
        self.assertRedirects(response, self.url)
        self.item.refresh_from_db()
        self.assertEqual(self.item.address, 'Новый адрес')
        response = self.client.post(self.url, {**data, 'map_url': 'invalid'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertTemplateUsed(response, 'home/furniture_base.html')
        self.item.refresh_from_db()
        self.assertEqual(self.item.map_url, data['map_url'])
