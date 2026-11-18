from django.test import TestCase
from django.urls import reverse

from apps.products.models import AttributeType, AttributeValue, Category, Product, ProductAttribute, ProductGalleryImage
from apps.products.tests.image_fixtures import image_test_storage


class FurniturePortfolioTests(TestCase):
    def test_portfolio_has_its_own_url_and_empty_state(self):
        response = self.client.get(reverse('furniture_portfolio'))
        self.assertContains(response, 'Работы пока не опубликованы')
        self.assertContains(response, 'Посмотреть каталог мебели')
        self.assertContains(self.client.get('/'), 'id="portfolio"')
        self.assertContains(self.client.get('/sitemap-pages.xml'), '/portfolio/')
        for name in ('catalog:catalog', 'furniture_services', 'furniture_about'):
            self.assertContains(self.client.get(reverse(name)), 'href="/portfolio/"', count=2)

    def test_only_published_selected_works_with_photos_are_shown_and_filterable(self):
        image_test_storage(self, ['products/portfolio.jpg', 'products/gallery/work.jpg'])
        wardrobes = Category.objects.create(title='Шкафы', slug='wardrobes-work')
        kitchens = Category.objects.create(title='Кухни', slug='kitchens-work')
        work = Product.objects.create(
            title='Шкаф у окна', slug='work-wardrobe', price=100000, image='products/portfolio.jpg',
            category=wardrobes, is_portfolio=True,
        )
        gallery_work = Product.objects.create(
            title='Кухня на заказ', slug='work-kitchen', price=80000, category=kitchens, is_portfolio=True,
        )
        ProductGalleryImage.objects.create(product=gallery_work, image='products/gallery/work.jpg')
        Product.objects.create(title='Без фото', slug='without-photo', price=1, is_portfolio=True)
        Product.objects.create(
            title='Черновая работа', slug='unpublished-work', price=1,
            image='products/portfolio.jpg', is_portfolio=True, is_active=False,
        )
        Product.objects.create(
            title='Просто изделие', slug='only-catalog', price=1,
            image='products/portfolio.jpg', is_featured=True,
        )

        url = reverse('furniture_portfolio')
        response = self.client.get(url)
        self.assertEqual(list(response.context['page_obj']), [gallery_work, work])
        self.assertContains(response, 'Ориентир по цене')
        self.assertContains(response, reverse('appointments:car_inquiry', args=[work.pk]) + '?type=similar')
        self.assertContains(response, work.get_absolute_url())
        self.assertEqual(list(self.client.get(url, {'category': kitchens.slug}).context['page_obj']), [gallery_work])

    def test_home_shows_selected_completed_work_and_its_specifications(self):
        image_test_storage(self, ['products/home-project.jpg'])
        work = Product.objects.create(
            title='Реальная гардеробная', slug='home-completed', price=120000,
            image='products/home-project.jpg', is_portfolio=True,
        )
        kind = AttributeType.objects.create(name='Материал', slug='portfolio-material')
        value = AttributeValue.objects.create(attribute_type=kind, value='Массив дуба')
        ProductAttribute.objects.create(product=work, attribute_type=kind, attribute_value=value)
        response = self.client.get('/')
        self.assertContains(response, 'id="completed-projects"', count=1)
        self.assertContains(response, 'Массив дуба')
        self.assertContains(response, reverse('appointments:car_inquiry', args=[work.pk]) + '?type=similar')
        work.is_active = False
        work.save(update_fields=['is_active'])
        self.assertNotContains(self.client.get('/'), 'id="completed-projects"')
