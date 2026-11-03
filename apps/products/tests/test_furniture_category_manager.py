"""Furniture categories: preserved identifiers, links and guarded deletion."""
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.products.furniture_categories import furniture_category_urls
from apps.products.models import Category, Product


class FurnitureCategoryManagerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('furniture-category-manager')
        self.user.profile.role = 'manager'
        self.user.profile.save()
        self.client.force_login(self.user)
        self.category = Category.objects.create(title='Шкафы', slug='shkafy')
        self.other = Category.objects.create(title='Кухни', slug='kuhni')
        self.product = Product.objects.create(title='Шкаф для прихожей', slug='hall-wardrobe',
            price=50000, category=self.category, is_active=False)
        self.list_url = reverse('catalog:category_list_manage')

    def url(self, action, category=None):
        return reverse('catalog:category_' + action, args=[(category or self.category).pk])

    def test_list_counts_include_drafts_and_catalog_link_uses_existing_id(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LUSTRID.RU')
        self.assertContains(response, 'Категории мебели')
        self.assertNotContains(response, 'Автомобилей')
        row = next(x for x in response.context['categories'] if x.pk == self.category.pk)
        self.assertEqual(row.product_count, 1)
        self.assertContains(response, reverse('catalog:catalog') + '?category=' + str(self.category.pk))
        self.assertContains(response, 'неопубликованные')
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertEqual(soup.find('a', href=self.url('edit')).get_text(), self.category.title)

    def test_gets_do_not_modify_home_links_categories_or_assignments(self):
        before = list(Category.objects.order_by('pk').values())
        products = list(Product.objects.values())
        links = furniture_category_urls()
        for url in (self.list_url, reverse('catalog:category_create'), self.url('edit'), self.url('delete')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'LUSTRID.RU')
            self.assertContains(response, 'noindex, nofollow')
        self.assertEqual(list(Category.objects.order_by('pk').values()), before)
        self.assertEqual(list(Product.objects.values()), products)
        self.assertEqual(furniture_category_urls(), links)

    def test_warning_for_home_category_survives_invalid_edit(self):
        self.assertContains(self.client.get(self.url('edit')), 'Изменение её названия или кода отключит этот переход')
        response = self.client.post(self.url('edit'), {'title': 'Изменённое название', 'slug': self.other.slug})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertContains(response, 'Категория связана с карточкой на главной')
        self.category.refresh_from_db()
        self.assertEqual((self.category.title, self.category.slug), ('Шкафы', 'shkafy'))
        custom = Category.objects.create(title='Тестовая мебель', slug='test-mebel')
        self.assertNotContains(self.client.get(self.url('edit', custom)), 'Категория связана с карточкой на главной')

    def test_create_edit_and_validation_without_javascript_preserve_product_links(self):
        response = self.client.post(reverse('catalog:category_create'), {'title': 'Мебель для кафе', 'slug': ''})
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)
        category = Category.objects.get(title='Мебель для кафе')
        self.assertEqual(category.slug, 'mebel-dlya-kafe')
        self.product.category = category
        self.product.save(update_fields=['category'])
        old_id = category.pk
        response = self.client.post(self.url('edit', category), {'title': 'Мебель для бизнеса', 'slug': category.slug})
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        category.refresh_from_db()
        self.assertEqual((category.pk, category.slug), (old_id, 'mebel-dlya-kafe'))
        self.assertEqual(self.product.category_id, old_id)
        response = self.client.post(self.url('edit', category), {'title': '', 'slug': category.slug})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertContains(response, 'aria-invalid="true"')

    def test_occupied_category_cannot_be_deleted_even_by_forged_post(self):
        response = self.client.get(self.url('delete'))
        self.assertContains(response, 'Удаление недоступно')
        self.assertNotContains(response, 'Удалить пустую категорию')
        response = self.client.post(self.url('delete'), follow=True)
        self.assertContains(response, 'Сначала перенесите изделия')
        self.product.refresh_from_db()
        self.assertEqual(self.product.category_id, self.category.pk)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        # An empty confirmation cannot bypass the server check if an item appears later.
        empty = Category.objects.create(title='Тест удаления', slug='empty-test')
        self.assertContains(self.client.get(self.url('delete', empty)), 'Удалить пустую категорию')
        self.product.category = empty
        self.product.save(update_fields=['category'])
        self.client.post(self.url('delete', empty))
        self.assertTrue(Category.objects.filter(pk=empty.pk).exists())

    def test_csrf_roles_and_empty_delete_only_after_post(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(self.url('delete', self.other)).status_code, 403)
        for role in ('customer', 'consultant'):
            user = get_user_model().objects.create_user(role, is_staff=True)
            user.profile.role = role
            user.profile.save()
            self.client.force_login(user)
            for url in (self.list_url, self.url('edit'), self.url('delete')):
                self.assertEqual(self.client.get(url).status_code, 302)
            self.assertEqual(self.client.post(self.url('delete', self.other)).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(self.list_url).status_code, 302)
        self.assertTrue(Category.objects.filter(pk=self.other.pk).exists())
        superuser = get_user_model().objects.create_superuser('super', password='test-only')
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.assertEqual(self.client.get(self.url('delete', self.other)).status_code, 200)
        self.assertTrue(Category.objects.filter(pk=self.other.pk).exists())
        self.client.post(self.url('delete', self.other))
        self.assertFalse(Category.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
