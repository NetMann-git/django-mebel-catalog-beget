"""шаг 26: preserve authentication, CSRF and redirect behavior while restyling."""
from html.parser import HTMLParser
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class Inputs(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.fields = {}
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name'):
            self.fields[attrs['name']] = attrs


class FurnitureLoginTests(TestCase):
    def setUp(self):
        self.url = reverse('users:login')
        self.user = get_user_model().objects.create_user('workshop-client', password='test-password-only')

    def test_get_keeps_links_next_and_credentials_controls(self):
        target = reverse('catalog:product_list_manage')
        response = self.client.get(self.url, {'next': target})
        self.assertEqual(response.status_code, 200)
        for text in ['furniture-login.css', 'furniture-reference.css', 'LUSTRID.RU',
                     'name="robots" content="noindex, nofollow"', 'width=device-width',
                     reverse('users:password_reset'), reverse('users:register')]:
            self.assertContains(response, text)
        self.assertNotContains(response, 'themes/auto.css')
        fields = Inputs(response).fields
        self.assertEqual(fields['next']['value'], target)
        self.assertEqual(fields['username']['autocomplete'], 'username')
        self.assertEqual(fields['password']['autocomplete'], 'current-password')
        self.assertNotIn('value', fields['password'])
        self.assertIn('csrfmiddlewaretoken', fields)

    def test_valid_login_honors_local_next_and_default_dashboard(self):
        for target in ['', reverse('catalog:catalog') + '?category=1']:
            self.client.logout()
            response = self.client.post(self.url, {'username': self.user.username,
                'password': 'test-password-only', 'next': target})
            self.assertRedirects(response, target or '/account/dashboard/', fetch_redirect_response=False)
            self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_external_next_is_not_followed(self):
        response = self.client.post(self.url, {'username': self.user.username,
            'password': 'test-password-only', 'next': 'https://untrusted.example/path'})
        self.assertRedirects(response, '/account/dashboard/', fetch_redirect_response=False)

    def test_invalid_credentials_keep_username_but_never_password(self):
        response = self.client.post(self.url, {'username': self.user.username, 'password': 'wrong-secret-only',
                                               'next': reverse('catalog:catalog')})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Неверное имя пользователя или пароль.')
        self.assertEqual(Inputs(response).fields['username']['value'], self.user.username)
        self.assertNotIn('value', Inputs(response).fields['password'])
        self.assertNotContains(response, 'wrong-secret-only')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_and_missing_fields_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        for data in [{}, {'username': self.user.username, 'password': 'test-password-only'}]:
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Неверное имя пользователя или пароль.')
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_csrf_required_and_valid_token_allows_login(self):
        client = Client(enforce_csrf_checks=True)
        credentials = {'username': self.user.username, 'password': 'test-password-only'}
        self.assertEqual(client.post(self.url, credentials).status_code, 403)
        response = client.get(self.url)
        token = Inputs(response).fields['csrfmiddlewaretoken']['value']
        self.assertEqual(client.post(self.url, {**credentials, 'csrfmiddlewaretoken': token}).status_code, 302)

    def test_bound_username_is_escaped_and_get_does_not_change_user(self):
        response = self.client.post(self.url, {'username': '\"><b>name</b>', 'password': 'wrong'})
        self.assertContains(response, '&lt;b&gt;name&lt;/b&gt;')
        self.assertNotContains(response, '<b>name</b>')
        self.client.get(self.url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('test-password-only'))
        self.assertEqual(get_user_model().objects.count(), 1)
