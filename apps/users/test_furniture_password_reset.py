"""шаг 28: preserve the complete Django password recovery flow."""
import re
from urllib.parse import urlsplit
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from apps.users.test_furniture_login import Inputs


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class FurniturePasswordResetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reset-client', email='client@example.test', password='Old-test-only-28!')
        self.url = reverse('users:password_reset')
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))

    def reset_link(self):
        token = default_token_generator.make_token(self.user)
        return reverse('users:password_reset_confirm', kwargs={'uidb64': self.uid, 'token': token})

    def test_all_states_use_furniture_shell_and_preserve_links(self):
        for url in [self.url, reverse('users:password_reset_done'), reverse('users:password_reset_complete'),
                    reverse('users:password_reset_confirm', kwargs={'uidb64': self.uid, 'token': 'invalid'})]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            for text in ['furniture-login.css', 'furniture-reference.css', 'noindex, nofollow',
                         'width=device-width', reverse('users:login')]:
                self.assertContains(response, text)
            self.assertNotContains(response, 'themes/auto.css')

    def test_invalid_email_stays_on_form_and_password_is_unchanged(self):
        response = self.client.post(self.url, {'email': 'invalid'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertEqual(Inputs(response).fields['email']['value'], 'invalid')
        self.assertEqual(len(mail.outbox), 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Old-test-only-28!'))

    def test_request_sends_existing_template_and_unknown_email_has_same_public_response(self):
        for email in ['client@example.test', 'unknown@example.test']:
            response = self.client.post(self.url, {'email': email})
            self.assertRedirects(response, reverse('users:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['client@example.test'])
        self.assertIn('Восстановление пароля', message.subject)
        self.assertRegex(message.body, r'http://testserver/account/reset/[\w-]+/[\w-]+/')
        self.assertNotIn('Old-test-only-28!', message.body)

    def test_complete_flow_validates_password_and_token_cannot_be_reused(self):
        self.client.post(self.url, {'email': self.user.email})
        link = re.search(r'http://testserver/account/reset/[\w-]+/[\w-]+/', mail.outbox[0].body).group()
        raw_path = urlsplit(link).path
        redirect = self.client.get(raw_path)
        self.assertEqual(redirect.status_code, 302)
        form_path = redirect['Location']
        self.assertIn('/set-password/', form_path)
        response = self.client.get(form_path)
        self.assertTrue(response.context['validlink'])
        self.assertContains(response, 'id="id_new_password1_helptext"')
        for data in [{'new_password1': 'New-test-only-28!', 'new_password2': 'Mismatch-only-28!'},
                     {'new_password1': '123', 'new_password2': '123'}]:
            response = self.client.post(form_path, data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            self.assertNotIn('value', Inputs(response).fields['new_password1'])
        response = self.client.post(form_path, {'new_password1': 'New-test-only-28!', 'new_password2': 'New-test-only-28!'})
        self.assertRedirects(response, reverse('users:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-test-only-28!'))
        self.assertFalse(self.user.check_password('Old-test-only-28!'))
        self.assertNotIn('_auth_user_id', self.client.session)
        reused = Client().get(raw_path)
        self.assertEqual(reused.status_code, 200)
        self.assertFalse(reused.context['validlink'])
        self.assertNotIn('new_password1', Inputs(reused).fields)

    def test_invalid_and_expired_tokens_do_not_expose_change_form(self):
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            response = self.client.get(self.reset_link())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['validlink'])
        self.assertContains(response, 'Запросить новую ссылку')
        self.assertNotIn('new_password1', Inputs(response).fields)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Old-test-only-28!'))

    def test_inactive_or_unusable_accounts_do_not_receive_reset_emails(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.client.post(self.url, {'email': self.user.email})
        self.user.is_active = True
        self.user.set_unusable_password()
        self.user.save()
        self.client.post(self.url, {'email': self.user.email})
        self.assertEqual(len(mail.outbox), 0)

    def test_csrf_is_required_for_request_and_change_form(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, {'email': self.user.email}).status_code, 403)
        token = Inputs(client.get(self.url)).fields['csrfmiddlewaretoken']['value']
        self.assertEqual(client.post(self.url, {'email': self.user.email, 'csrfmiddlewaretoken': token}).status_code, 302)
        response = client.get(self.reset_link(), follow=True)
        path = response.redirect_chain[-1][0]
        data = {'new_password1': 'New-test-only-28!', 'new_password2': 'New-test-only-28!'}
        self.assertEqual(client.post(path, data).status_code, 403)
        token = Inputs(client.get(path)).fields['csrfmiddlewaretoken']['value']
        self.assertEqual(client.post(path, {**data, 'csrfmiddlewaretoken': token}).status_code, 302)
