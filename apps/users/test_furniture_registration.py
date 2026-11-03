"""шаг 27: keep existing registration validation, profile and login contracts."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.users.models import Profile
from apps.users.test_furniture_login import Inputs


class FurnitureRegistrationTests(TestCase):
    def setUp(self):
        self.url = reverse('users:register')
        self.data = {'username': 'new-workshop-client', 'email': 'client@example.test',
                     'first_name': 'Иван', 'last_name': 'Иванов',
                     'password1': 'Test-only-strong-27!', 'password2': 'Test-only-strong-27!'}

    def test_get_preserves_all_fields_and_displays_password_help(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        fields = Inputs(response).fields
        self.assertEqual(set(fields), set(self.data) | {'csrfmiddlewaretoken'})
        for name in self.data:
            self.assertIn('required', fields[name])
        for text in ['furniture-login.css', 'furniture-reference.css', 'LUSTRID.RU',
                     'name="robots" content="noindex, nofollow"', 'width=device-width',
                     'id="id_password1_helptext"', reverse('users:login')]:
            self.assertContains(response, text)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_registration_creates_customer_profile_and_logs_in(self):
        response = self.client.post(self.url, self.data)
        self.assertRedirects(response, reverse('users:dashboard'), fetch_redirect_response=False)
        user = get_user_model().objects.get(username=self.data['username'])
        self.assertTrue(user.check_password(self.data['password1']))
        self.assertEqual(user.email, self.data['email'])
        self.assertEqual(user.first_name, self.data['first_name'])
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(Profile.objects.get(user=user).role, 'customer')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_invalid_data_stays_on_form_without_creating_user_or_revealing_password(self):
        for overrides in [{'email': 'invalid'}, {'password2': 'Mismatch-27!'},
                          {'first_name': ''}, {'password1': '123', 'password2': '123'}]:
            with self.subTest(overrides=overrides):
                data = {**self.data, **overrides}
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertContains(response, 'Проверьте отмеченные поля.')
                fields = Inputs(response).fields
                self.assertEqual(fields['username']['value'], self.data['username'])
                for name in ['password1', 'password2']:
                    self.assertNotIn('value', fields[name])
                self.assertEqual(get_user_model().objects.count(), 0)
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_duplicate_username_does_not_overwrite_existing_user(self):
        user = get_user_model().objects.create_user(self.data['username'], email='original@example.test', password='Original-only-27!')
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(get_user_model().objects.count(), 1)
        user.refresh_from_db()
        self.assertEqual(user.email, 'original@example.test')
        self.assertTrue(user.check_password('Original-only-27!'))

    def test_csrf_is_required_and_valid_token_allows_registration(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, self.data).status_code, 403)
        token = Inputs(client.get(self.url)).fields['csrfmiddlewaretoken']['value']
        self.assertEqual(client.post(self.url, {**self.data, 'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_authenticated_user_is_redirected_without_creating_another_account(self):
        user = get_user_model().objects.create_user('existing-client', password='test-only')
        self.client.force_login(user)
        for method in ['get', 'post']:
            response = getattr(self.client, method)(self.url, self.data if method == 'post' else {})
            self.assertRedirects(response, reverse('users:dashboard'), fetch_redirect_response=False)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_bound_name_is_escaped(self):
        response = self.client.post(self.url, {**self.data, 'first_name': '<b>Имя</b>', 'email': 'invalid'})
        self.assertContains(response, '&lt;b&gt;Имя&lt;/b&gt;')
        self.assertNotContains(response, '<b>Имя</b>')
