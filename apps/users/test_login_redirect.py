"""шаг 30: protected pages must reach the real login and retain next."""
from urllib.parse import parse_qs, urlsplit
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.users.test_furniture_login import Inputs


class LoginRedirectTests(TestCase):
    def test_guest_redirects_reach_login_with_original_path_and_query(self):
        names = ['users:dashboard', 'users:profile_edit', 'users:appointments',
                 'users:reviews', 'users:manager_dashboard',
                 'users:consultant_dashboard', 'users:consultant_calendar',
                 'users:consultant_create_appointment']
        for name in names:
            target = reverse(name) + '?page=2&filter=oak'
            with self.subTest(target=target):
                response = self.client.get(target)
                self.assertEqual(response.status_code, 302)
                location = urlsplit(response['Location'])
                self.assertEqual(location.path, reverse('users:login'))
                self.assertEqual(parse_qs(location.query)['next'], [target])
                login = self.client.get(response['Location'])
                self.assertEqual(login.status_code, 200)
                self.assertEqual(Inputs(login).fields['next']['value'], target)
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_returns_to_requested_dashboard_without_redirect_loop(self):
        user = get_user_model().objects.create_user('redirect-client', password='test-only-30')
        target = reverse('users:dashboard') + '?page=2&filter=oak'
        response = self.client.get(target, follow=True)
        self.assertEqual(len(response.redirect_chain), 1)
        next_value = Inputs(response).fields['next']['value']
        response = self.client.post(reverse('users:login'), {
            'username': user.username, 'password': 'test-only-30', 'next': next_value}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(target, 302)])
        self.assertContains(response, user.username)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_customer_still_cannot_enter_manager_page_after_login(self):
        user = get_user_model().objects.create_user('ordinary-client', password='test-only-30')
        target = reverse('users:manager_dashboard')
        login = self.client.get(target, follow=True)
        next_value = Inputs(login).fields['next']['value']
        response = self.client.post(reverse('users:login'), {
            'username': user.username, 'password': 'test-only-30', 'next': next_value}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(target, 302), (reverse('users:dashboard'), 302)])
        self.assertContains(response, 'У вас нет доступа')
        self.assertNotContains(response, 'Управление мастерской')
        self.assertFalse(user.is_staff)

    def test_invalid_credentials_keep_next_and_external_next_is_rejected(self):
        user = get_user_model().objects.create_user('safe-client', password='test-only-30')
        target = reverse('users:dashboard') + '?page=2'
        login = self.client.get(target, follow=True)
        response = self.client.post(reverse('users:login'), {
            'username': user.username, 'password': 'wrong-only', 'next': Inputs(login).fields['next']['value']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Inputs(response).fields['next']['value'], target)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('users:login'), {
            'username': user.username, 'password': 'test-only-30', 'next': 'https://untrusted.example/path'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('users:dashboard'))
