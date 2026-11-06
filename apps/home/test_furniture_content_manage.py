"""Content editors use the furniture shell and retain their actions."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import ClientShowcase, TeamMember


class FurnitureContentManageTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('content-manager')
        user.profile.role = 'manager'; user.profile.save()
        self.client.force_login(user)
        self.customer = ClientShowcase.objects.create(name='Клиент мастерской', vehicle='Кухня', sort_order=1000)
        self.member = TeamMember.objects.create(name='Мастер', position='Столяр', sort_order=1000)

    def test_lists_create_edit_forms_have_new_shell_and_navigation(self):
        urls = [reverse('home:client_list_manage'), reverse('home:client_create'),
                reverse('home:client_edit', args=[self.customer.pk]), reverse('home:team_list_manage'),
                reverse('home:team_create'), reverse('home:team_edit', args=[self.member.pk])]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'home/furniture_base.html')
                self.assertContains(response, 'furniture-content-manage.css')
                self.assertContains(response, reverse('users:manager_dashboard'))
                self.assertNotContains(response, 'home/css/client-manage.css')
                self.assertNotContains(response, 'themes/auto.css')
                self.assertContains(response, 'noindex, nofollow')

    def test_searches_and_reorder_scripts_remain(self):
        for url, name, script in [('client_list_manage', self.customer.name, 'client-manage.js'),
                                  ('team_list_manage', self.member.name, 'team-manage.js')]:
            response = self.client.get(reverse('home:'+url), {'search': name})
            self.assertContains(response, name)
            self.assertContains(response, script)

    def test_invalid_forms_show_errors_in_new_shell_without_saving(self):
        for url in ['client_create', 'team_create']:
            response = self.client.post(reverse('home:'+url), {'name': ''})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            self.assertTemplateUsed(response, 'home/furniture_base.html')

    def test_team_move_with_isolated_test_records(self):
        TeamMember.objects.exclude(pk=self.member.pk).delete()
        other = TeamMember.objects.create(name='Второй мастер', position='Столяр', sort_order=2000)
        response = self.client.post(reverse('home:team_move', args=[self.member.pk]), {'direction': 'down'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(TeamMember.objects.values_list('pk', flat=True)), [other.pk, self.member.pk])
