"""шаг 29: personal counters, role links and POST logout remain available."""
from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.appointments.models import Appointment
from apps.products.models import Product
from apps.reviews.models import Review
from apps.wishlist.models import Favorite
from apps.users.test_furniture_login import Inputs


class FurnitureDashboardTests(TestCase):
    def setUp(self):
        self.url = reverse('users:dashboard')
        self.user = get_user_model().objects.create_user('cabinet-client', password='test-only')
        self.other = get_user_model().objects.create_user('other-private-client', password='test-only')
        self.product = Product.objects.create(title='Шкаф', slug='cabinet-case', price=100)

    def test_guest_is_redirected_without_personal_data(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response['Location'])
        self.assertNotContains(response, self.user.username, status_code=302)

    def test_personal_counts_and_all_existing_customer_links(self):
        for index, user in enumerate([self.user, self.other]):
            Favorite.objects.create(user=user, product=self.product)
            Review.objects.create(user=user, product=self.product, rating=5, text='Отзыв')
            Appointment.objects.create(user=user, name=user.username, phone='000', date=date(2026, 11, 4), time=time(12 + index))
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for key in ['appointments_count', 'favorites_count', 'reviews_count']:
            self.assertEqual(response.context[key], 1)
        for name in ['users:appointments', 'users:favorites', 'users:reviews', 'users:profile_edit', 'catalog:catalog']:
            self.assertContains(response, f'href="{reverse(name)}"')
        for text in ['furniture-dashboard.css', 'furniture-reference.css', 'noindex, nofollow', 'width=device-width', self.user.username]:
            self.assertContains(response, text)
        self.assertNotContains(response, self.other.username)
        self.assertNotContains(response, 'themes/auto.css')
        self.assertContains(response, 'data-smart-search-input', count=1)
        self.assertContains(response, 'aria-controls="cabinet-search-suggestions"', count=1)
        self.assertContains(response, '<script src="/static/search/js/search.js" defer></script>', count=1)
        self.assertEqual(Favorite.objects.count(), 2)
        self.assertEqual(Review.objects.count(), 2)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_role_links_keep_the_existing_visibility_rules(self):
        manager_names = ['users:manager_dashboard', 'home:client_list_manage', 'home:team_list_manage', 'home:contacts_manage']
        self.client.force_login(self.user)
        for role in ['customer', 'consultant', 'manager', 'admin']:
            self.user.profile.role = role
            self.user.profile.save(update_fields=['role'])
            response = self.client.get(self.url)
            for name in manager_names:
                assertion = self.assertContains if role in ['manager', 'admin'] else self.assertNotContains
                assertion(response, f'href="{reverse(name)}"')
            assertion = self.assertContains if role != 'customer' else self.assertNotContains
            assertion(response, f'href="{reverse("users:consultant_dashboard")}"')
        self.user.profile.role = 'customer'
        self.user.profile.save(update_fields=['role'])
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        response = self.client.get(self.url)
        for name in manager_names:
            self.assertContains(response, f'href="{reverse(name)}"')

    def test_zero_state_and_username_escaping(self):
        self.user.username = '<b>client</b>'
        self.user.save(update_fields=['username'])
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;b&gt;client&lt;/b&gt;')
        self.assertNotContains(response, '<b>client</b>')
        for key in ['appointments_count', 'favorites_count', 'reviews_count']:
            self.assertEqual(response.context[key], 0)

    def test_logout_keeps_post_and_csrf_contract(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(self.url)
        token = Inputs(response).fields['csrfmiddlewaretoken']['value']
        logout = reverse('users:logout')
        self.assertContains(response, f'action="{logout}"')
        self.assertEqual(client.get(logout).status_code, 405)
        self.assertEqual(client.post(logout).status_code, 403)
        self.assertIn('_auth_user_id', client.session)
        self.assertEqual(client.post(logout, {'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertNotIn('_auth_user_id', client.session)
