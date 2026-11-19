from django.contrib.admin.sites import AdminSite
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.products.admin import ProductAdmin
from apps.products.forms import ProductForm
from apps.products.models import Product, ProductGalleryImage
from apps.products.tests.image_fixtures import image_test_storage


class ProjectStoryTests(TestCase):
    def setUp(self):
        image_test_storage(self, ['products/work.jpg', 'products/detail.jpg'])
        self.work = Product.objects.create(
            title='Кухня у окна', slug='kitchen-by-window', price=150000,
            image='products/work.jpg', is_portfolio=True,
            project_task='Разместить кухню вокруг низкого окна',
            project_solution='Снизили рабочую секцию у окна',
            project_dimensions='Основной ряд 3200 мм, высота 2400 мм',
            project_materials='Фасады МДФ в эмали, корпус ЛДСП',
            price_details='Корпус и фасады включены. Доставка отдельно.',
        )
        ProductGalleryImage.objects.create(product=self.work, image='products/detail.jpg', alt='Выдвижной механизм в угловой секции')

    def test_work_story_gallery_price_and_similar_request(self):
        response = self.client.get(self.work.get_absolute_url())
        for text in ['Проект в деталях', 'Задача клиента', 'Решение мастерской', self.work.project_task, self.work.project_dimensions, self.work.project_materials, self.work.price_details]:
            self.assertContains(response, text)
        self.assertContains(response, 'id="project-photo-caption"')
        self.assertContains(response, 'Ориентир стоимости проекта')
        self.assertNotContains(response, 'Заказать изготовление')
        self.assertEqual(len(response.context['furniture_photos']), 2)
        self.assertContains(response, reverse('appointments:car_inquiry', args=[self.work.pk]) + '?type=similar')
        response = self.client.get(reverse('furniture_portfolio'))
        self.assertContains(response, self.work.project_task)
        self.assertContains(response, 'srcset=')

    def test_story_not_exposed_for_regular_items_or_hidden_work(self):
        self.work.is_portfolio = False
        self.work.save()
        response = self.client.get(self.work.get_absolute_url())
        self.assertNotContains(response, 'id="project-story-public"')
        self.assertNotContains(response, self.work.project_task)
        self.work.is_active = False
        self.work.save()
        self.assertEqual(self.client.get(self.work.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse('furniture_portfolio')), self.work.title)

    def test_old_work_without_story_still_opens_and_html_is_escaped(self):
        self.work.project_task = '<script>alert(1)</script>'
        self.work.project_solution = ''
        self.work.project_dimensions = ''
        self.work.project_materials = ''
        self.work.save()
        response = self.client.get(self.work.get_absolute_url())
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.work.project_task = ''
        self.work.save()
        self.assertContains(self.client.get(self.work.get_absolute_url()), 'Фотографии, описание и характеристики выполненного изделия')

    def test_manager_form_and_admin_save_project_fields(self):
        data = {'title':self.work.title, 'slug':self.work.slug, 'price':'150000', 'currency':'RUB', 'availability_status':'under_order',
                'is_active':'on', 'is_portfolio':'on', 'project_task':'Новая задача', 'project_solution':'Новое решение',
                'project_dimensions':'3000 мм', 'project_materials':'Массив дуба'}
        form = ProductForm(data=data, instance=self.work)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.work.refresh_from_db()
        self.assertEqual(self.work.project_solution, 'Новое решение')
        names = {n for _, options in ProductAdmin(Product, AdminSite()).fieldsets for n in options['fields']}
        self.assertTrue({'project_task','project_solution','project_dimensions','project_materials'} <= names)
        data['project_task'] = 'я' * 2501
        self.assertFalse(ProductForm(data=data, instance=self.work).is_valid())

    def test_real_editors_and_preview_show_story_fields(self):
        user = get_user_model().objects.create_superuser('project-editor', password='test-only')
        self.client.force_login(user)
        response = self.client.get(reverse('catalog:product_edit', args=[self.work.pk]))
        for name in ('project_task', 'project_solution', 'project_dimensions', 'project_materials'):
            self.assertContains(response, 'id="id_' + name + '"', count=1)
        response = self.client.get(reverse('catalog:product_preview', args=[self.work.pk]))
        self.assertContains(response, self.work.project_task)
        self.assertContains(response, 'noindex, nofollow')
        request = RequestFactory().get('/')
        request.user = user
        form = ProductAdmin(Product, AdminSite()).get_form(request, self.work)
        self.assertIn('project_solution', form.base_fields)
