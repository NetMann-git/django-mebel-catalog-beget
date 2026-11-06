from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.users.constants import ROLE_CUSTOMER, ROLE_MANAGER

from .models import ClientShowcase, ContactSettings, TeamMember


class ClientShowcaseTests(TestCase):
    def setUp(self):
        # Historical migrations seed auto-site cards; each scenario owns its fixtures.
        ClientShowcase.objects.all().delete()

    def create_user(self, username, role):
        user = get_user_model().objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save(update_fields=("role",))
        return user

    def test_furniture_home_does_not_publish_legacy_auto_client_cards(self):
        ClientShowcase.objects.create(name="Виден", vehicle="KIA", legacy_image="x.webp", is_published=True)
        ClientShowcase.objects.create(name="Скрыт", vehicle="BMW", legacy_image="y.webp", is_published=False)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Категории мебели")
        self.assertNotContains(response, "Виден")
        self.assertNotContains(response, "Скрыт")
        self.assertEqual(ClientShowcase.objects.count(), 2)

    def test_manager_can_open_client_management(self):
        user = self.create_user("manager_clients", ROLE_MANAGER)
        self.client.force_login(user)
        response = self.client.get(reverse("home:client_list_manage"))
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_open_client_management(self):
        user = self.create_user("customer_clients", ROLE_CUSTOMER)
        self.client.force_login(user)
        response = self.client.get(reverse("home:client_list_manage"))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_reorder_all_clients(self):
        first = ClientShowcase.objects.create(name="Первый", vehicle="KIA", sort_order=10)
        second = ClientShowcase.objects.create(name="Второй", vehicle="BMW", sort_order=20)
        third = ClientShowcase.objects.create(name="Третий", vehicle="Audi", sort_order=30)

        user = self.create_user("manager_reorder", ROLE_MANAGER)
        self.client.force_login(user)
        response = self.client.post(
            reverse("home:client_reorder"),
            {"ordered_ids": f"{third.id},{first.id},{second.id}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(ClientShowcase.objects.values_list("id", flat=True)),
            [third.id, first.id, second.id],
        )

    def test_reorder_rejects_partial_list(self):
        first = ClientShowcase.objects.create(name="Первый", vehicle="KIA", sort_order=10)
        ClientShowcase.objects.create(name="Второй", vehicle="BMW", sort_order=20)

        user = self.create_user("manager_partial_reorder", ROLE_MANAGER)
        self.client.force_login(user)
        response = self.client.post(reverse("home:client_reorder"), {"ordered_ids": str(first.id)})

        self.assertEqual(response.status_code, 409)

    def test_manager_can_delete_client(self):
        client = ClientShowcase.objects.create(name="Удалить", vehicle="Volvo", sort_order=10)
        user = self.create_user("manager_delete", ROLE_MANAGER)
        self.client.force_login(user)

        response = self.client.post(reverse("home:client_delete", args=[client.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ClientShowcase.objects.filter(pk=client.id).exists())

    def test_superuser_can_open_client_management_without_admin_profile_role(self):
        user = get_user_model().objects.create_superuser(
            username="root_clients",
            email="root@example.com",
            password="testpass123",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("home:client_list_manage"))
        self.assertEqual(response.status_code, 200)

    def test_manager_can_move_client_down_without_javascript(self):
        first = ClientShowcase.objects.create(name="Первый", vehicle="KIA", sort_order=10)
        second = ClientShowcase.objects.create(name="Второй", vehicle="BMW", sort_order=20)
        third = ClientShowcase.objects.create(name="Третий", vehicle="Audi", sort_order=30)

        user = self.create_user("manager_move", ROLE_MANAGER)
        self.client.force_login(user)
        response = self.client.post(
            reverse("home:client_move", args=[first.id]),
            {"direction": "down"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(ClientShowcase.objects.values_list("id", flat=True)),
            [second.id, first.id, third.id],
        )


class ClientVideoReviewTests(TestCase):
    def test_video_review_section_shows_only_published_clients_with_rutube(self):
        visible = ClientShowcase.objects.create(
            name="Видео клиент", vehicle="KIA", legacy_image="x.webp",
            rutube_url="https://rutube.ru/play/embed/b01059d843b5c69740fb2ae3d1cd682d/",
            is_published=True,
        )
        ClientShowcase.objects.create(
            name="Без видео", vehicle="BMW", legacy_image="y.webp", is_published=True,
        )
        ClientShowcase.objects.create(
            name="Скрытый видео", vehicle="Audi", legacy_image="z.webp",
            rutube_url="https://rutube.ru/play/embed/4217e2a2d92bf8fa77e850b174dc72ab/",
            is_published=False,
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, visible.rutube_url)
        self.assertNotContains(response, "Скрытый видео")

    def test_home_hides_video_review_section_when_no_video_clients(self):
        ClientShowcase.objects.create(
            name="Только фото", vehicle="BMW", legacy_image="x.webp", is_published=True,
        )

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Отзывы о нашей работе")

    def test_rutube_embed_url_rejects_non_rutube_host(self):
        client = ClientShowcase(rutube_url="https://example.com/play/embed/b01059d843b5c69740fb2ae3d1cd682d/")
        self.assertEqual(client.rutube_embed_url, "")


class ClientMediaRulesTests(TestCase):
    def test_client_form_allows_video_without_photo(self):
        from apps.home.forms import ClientShowcaseForm

        form = ClientShowcaseForm(
            data={
                "name": "Оксана",
                "vehicle": "Changan UNI-T",
                "rutube_url": "https://rutube.ru/play/embed/f44e2211a5634fc5d83109157463b3c2/",
                "sort_order": 100,
                "is_published": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_home_separates_photo_clients_and_video_clients(self):
        from django.test import RequestFactory
        from apps.home.context import HomeContextBuilder

        photo_only = ClientShowcase.objects.create(
            name="Фото",
            vehicle="Авто 1",
            image="home/clients/test.webp",
            is_published=True,
        )
        video_only = ClientShowcase.objects.create(
            name="Видео",
            vehicle="Авто 2",
            rutube_url="https://rutube.ru/play/embed/f44e2211a5634fc5d83109157463b3c2/",
            is_published=True,
        )

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.session = {}

        with patch("apps.home.context.CatalogRepository.featured", return_value=[]):
            context = HomeContextBuilder.build(request)

        self.assertIn(photo_only, context["clients"])
        self.assertNotIn(video_only, context["clients"])
        self.assertIn(video_only, context["video_clients"])


class TeamMemberTests(TestCase):
    def create_user(self, username, role):
        user = get_user_model().objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save(update_fields=("role",))
        return user

    def test_home_shows_only_published_team_members(self):
        TeamMember.objects.create(name="Виден", position="Менеджер", legacy_image="x.webp", is_published=True)
        TeamMember.objects.create(name="Скрыт", position="Менеджер", legacy_image="y.webp", is_published=False)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Виден")
        self.assertNotContains(response, "Скрыт")

    def test_manager_can_open_team_management(self):
        user = self.create_user("manager_team", ROLE_MANAGER)
        self.client.force_login(user)
        response = self.client.get(reverse("home:team_list_manage"))
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_open_team_management(self):
        user = self.create_user("customer_team", ROLE_CUSTOMER)
        self.client.force_login(user)
        response = self.client.get(reverse("home:team_list_manage"))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_move_team_member(self):
        first = TeamMember.objects.create(name="Первый", position="Менеджер", legacy_image="a.webp", sort_order=10)
        second = TeamMember.objects.create(name="Второй", position="Менеджер", legacy_image="b.webp", sort_order=20)
        user = self.create_user("manager_team_move", ROLE_MANAGER)
        self.client.force_login(user)
        response = self.client.post(reverse("home:team_move", args=[first.id]), {"direction": "down"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(TeamMember.objects.values_list("id", flat=True)), [second.id, first.id])

    def test_superuser_can_open_team_management(self):
        user = get_user_model().objects.create_superuser(username="root_team", email="root-team@example.com", password="testpass123")
        self.client.force_login(user)
        response = self.client.get(reverse("home:team_list_manage"))
        self.assertEqual(response.status_code, 200)


class ContactSettingsTests(TestCase):
    def create_user(self, username, role):
        user = get_user_model().objects.create_user(username=username, password="testpass123")
        user.profile.role = role
        user.profile.save(update_fields=("role",))
        return user

    def test_home_uses_contact_settings(self):
        ContactSettings.objects.update_or_create(
            pk=1,
            defaults={
                "phone_primary": "+7 900 111-22-33",
                "address": "Тестовый адрес",
                "map_url": "https://yandex.ru/map-widget/v1/?z=12",
                "is_published": True,
            },
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, "+7 900 111-22-33")
        self.assertContains(response, "Тестовый адрес")

    def test_hidden_contacts_are_not_rendered(self):
        ContactSettings.objects.update_or_create(
            pk=1,
            defaults={
                "phone_primary": "+7 900 000-00-00",
                "address": "Скрытый адрес",
                "map_url": "https://yandex.ru/map-widget/v1/?z=12",
                "is_published": False,
            },
        )
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Скрытый адрес")

    def test_manager_can_edit_contacts(self):
        user = self.create_user("manager_contacts", ROLE_MANAGER)
        self.client.force_login(user)
        response = self.client.get(reverse("home:contacts_manage"))
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_edit_contacts(self):
        user = self.create_user("customer_contacts", ROLE_CUSTOMER)
        self.client.force_login(user)
        response = self.client.get(reverse("home:contacts_manage"))
        self.assertEqual(response.status_code, 302)
