"""шаг 31: profile validation, isolation and existing update contracts."""
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from apps.users.models import Profile
from apps.users.test_furniture_login import Inputs


class FurnitureProfileTests(TestCase):
    def setUp(self):
        self.url = reverse('users:profile_edit')
        self.user = get_user_model().objects.create_user('profile-owner', email='old@example.test',
            first_name='Иван', last_name='Иванов', password='test-only-31')
        self.user.profile.phone = '+7 000 000-00-00'
        self.user.profile.save()
        self.other = get_user_model().objects.create_user('other-profile', email='private@example.test', password='other-only')
        self.client.force_login(self.user)

    def test_get_displays_only_current_profile_and_keeps_optional_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        fields = Inputs(response).fields
        self.assertEqual(set(fields), {'first_name', 'last_name', 'email', 'phone', 'csrfmiddlewaretoken'})
        self.assertEqual(fields['email']['value'], self.user.email)
        for name in ['first_name', 'last_name', 'email', 'phone']:
            self.assertNotIn('required', fields[name])
        for text in ['furniture-login.css', 'furniture-reference.css', 'noindex, nofollow', reverse('users:dashboard')]:
            self.assertContains(response, text)
        self.assertNotContains(response, self.other.email)
        self.assertNotContains(response, 'themes/auto.css')

    def test_valid_update_does_not_change_privileges_password_or_another_user(self):
        response = self.client.post(self.url, {'first_name': 'Анна', 'last_name': 'Петрова',
            'email': 'new@example.test', 'phone': '+7 111 111-11-11',
            'user_id': self.other.pk, 'is_staff': '1', 'is_superuser': '1', 'role': 'admin', 'username': 'hacked'})
        self.assertRedirects(response, reverse('users:dashboard'), fetch_redirect_response=False)
        self.user.refresh_from_db(); self.other.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Анна')
        self.assertEqual(self.user.last_name, 'Петрова')
        self.assertEqual(self.user.email, 'new@example.test')
        self.assertEqual(self.user.profile.phone, '+7 111 111-11-11')
        self.assertEqual(self.user.username, 'profile-owner')
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertEqual(self.user.profile.role, 'customer')
        self.assertTrue(self.user.check_password('test-only-31'))
        self.assertEqual(self.other.email, 'private@example.test')

    def test_invalid_email_and_lengths_reject_entire_update(self):
        for overrides in [{'email': 'invalid'}, {'first_name': 'x' * 151},
                          {'last_name': 'x' * 151}, {'phone': '1' * 21}]:
            data = {'first_name': 'Новое имя', 'email': 'new@example.test', 'phone': '123', **overrides}
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            self.assertContains(response, 'Проверьте отмеченные поля.')
            self.user.refresh_from_db()
            self.assertEqual(self.user.first_name, 'Иван')
            self.assertEqual(self.user.email, 'old@example.test')
            self.assertEqual(self.user.profile.phone, '+7 000 000-00-00')

    def test_missing_fields_stay_unchanged_and_explicit_blanks_are_allowed(self):
        self.client.post(self.url, {'phone': '123'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old@example.test')
        self.assertEqual(self.user.first_name, 'Иван')
        self.assertEqual(self.user.profile.phone, '123')
        self.client.post(self.url, {'first_name': '', 'last_name': '', 'email': '', 'phone': ''})
        self.user.refresh_from_db()
        self.assertEqual([self.user.first_name, self.user.last_name, self.user.email, self.user.profile.phone], ['', '', '', ''])

    def test_guest_and_csrf_protection_are_preserved(self):
        guest = Client()
        self.assertEqual(guest.get(self.url).status_code, 302)
        self.assertEqual(guest.post(self.url, {'email': 'attack@example.test'}).status_code, 302)
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(self.url, {'phone': '123'}).status_code, 403)
        token = Inputs(client.get(self.url)).fields['csrfmiddlewaretoken']['value']
        self.assertEqual(client.post(self.url, {'phone': '123', 'csrfmiddlewaretoken': token}).status_code, 302)

    def test_user_update_rolls_back_if_profile_write_fails(self):
        original_save = Profile.save
        def fail_phone(instance, *args, **kwargs):
            if kwargs.get('update_fields') == ['phone']:
                raise IntegrityError('synthetic profile write failure')
            return original_save(instance, *args, **kwargs)
        with patch.object(Profile, 'save', fail_phone):
            with self.assertRaises(IntegrityError):
                self.client.post(self.url, {'email': 'new@example.test', 'phone': '123'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old@example.test')
        self.assertEqual(self.user.profile.phone, '+7 000 000-00-00')

    def test_bound_values_are_escaped_on_validation_error(self):
        response = self.client.post(self.url, {'first_name': '<b>Имя</b>', 'email': 'invalid'})
        self.assertContains(response, '&lt;b&gt;Имя&lt;/b&gt;')
        self.assertNotContains(response, '<b>Имя</b>')
