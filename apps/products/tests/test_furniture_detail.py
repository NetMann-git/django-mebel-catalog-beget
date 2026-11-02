"""Шаг 06: исходные фото, публикация, сохранение характеристик и формы изделия."""
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from apps.products.models import (Product, Category, ProductGalleryImage, AttributeType,
                                  AttributeValue, ProductAttribute, EquipmentGroup, EquipmentOption)
from apps.reviews.models import Review


class FurnitureDetailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(title='Шкафы', slug='shkafy')
        self.item = Product.objects.create(title='Шкаф под размер', slug='wardrobe-detail', price=120000,
                                          category=self.category, article='F-001', description='Описание изделия')

    def test_furniture_shell_original_currency_and_fallbacks(self):
        self.item.currency = 'EUR'
        self.item.save(update_fields=['currency'])
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заказать изготовление')
        self.assertContains(response, 'Уточнить стоимость')
        self.assertContains(response, 'Фотографии пока не добавлены')
        self.assertContains(response, '120\u00a0000 €')
        self.assertContains(response, 'furniture-detail.css')
        for text in ('Об автомобиле', 'Заказать это авто', '_catalog-car-card.css', 'themes/auto.css'):
            self.assertNotContains(response, text)

    def test_gallery_without_cover_uses_first_original_and_counts_correctly(self):
        ProductGalleryImage.objects.create(product=self.item, image='products/gallery/second.jpg', sort_order=2)
        ProductGalleryImage.objects.create(product=self.item, image='products/gallery/first.jpg', alt='Первая фотография', sort_order=1)
        response = self.client.get(self.item.get_absolute_url())
        photos = response.context['furniture_photos']
        self.assertEqual([p['image'].name for p in photos], ['products/gallery/first.jpg', 'products/gallery/second.jpg'])
        self.assertEqual(photos[0]['alt'], 'Первая фотография')
        self.assertContains(response, 'id="main-image" class="main-image" src="/media/products/gallery/first.jpg"')
        self.assertContains(response, 'id="total-photos">2</span>')
        self.assertNotContains(response, 'Фотографии пока не добавлены')

    def test_cover_is_first_and_repeated_filenames_are_not_counted_twice(self):
        self.item.image = 'products/cover.jpg'
        self.item.save(update_fields=['image'])
        for filename in ['products/cover.jpg', 'products/gallery/detail.jpg', 'products/gallery/detail.jpg']:
            ProductGalleryImage.objects.create(product=self.item, image=filename)
        photos = self.client.get(self.item.get_absolute_url()).context['furniture_photos']
        self.assertEqual([p['image'].name for p in photos], ['products/cover.jpg', 'products/gallery/detail.jpg'])

    def test_attributes_selected_equipment_and_seo_are_retained(self):
        self.item.meta_title = 'Индивидуальный шкаф — мастерская'
        self.item.meta_description = 'Описание для поиска'
        self.item.save(update_fields=['meta_title', 'meta_description'])
        kind = AttributeType.objects.create(name='Материал', slug='material')
        value = AttributeValue.objects.create(attribute_type=kind, value='Массив дуба')
        ProductAttribute.objects.create(product=self.item, attribute_type=kind, attribute_value=value)
        group = EquipmentGroup.objects.create(name='Фурнитура', slug='hardware')
        selected = EquipmentOption.objects.create(name='Петли с доводчиком', group=group)
        hidden = EquipmentOption.objects.create(name='Скрытая опция', group=group, is_active=False)
        self.item.equipment.set([selected, hidden])
        response = self.client.get(self.item.get_absolute_url())
        for text in ('Массив дуба', 'Петли с доводчиком', 'Индивидуальный шкаф — мастерская', 'Описание для поиска', 'F-001'):
            self.assertContains(response, text)
        self.assertNotContains(response, 'Скрытая опция')
        self.assertNotContains(response, 'VIN')

    def test_drafts_and_unpublished_reviews_are_not_exposed(self):
        Review.objects.create(product=self.item, guest_name='Клиент', rating=5, text='Опубликованный отзыв', is_published=True)
        Review.objects.create(product=self.item, guest_name='Скрыт', rating=1, text='Непубличный отзыв', is_published=False)
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, 'Опубликованный отзыв')
        self.assertNotContains(response, 'Непубличный отзыв')
        self.item.is_active = False
        self.item.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(self.item.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse('appointments:car_inquiry', args=[self.item.pk])).status_code, 404)

    def test_recent_history_favorites_and_csrf_remain_available(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(self.item.get_absolute_url())
        self.assertIn(self.item.pk, client.session['recently_viewed'])
        token = client.cookies['csrftoken'].value
        favorite = reverse('wishlist:toggle', args=[self.item.pk])
        comparison = reverse('catalog:toggle_comparison_ajax', args=[self.item.pk])
        self.assertTrue(client.post(favorite, HTTP_X_CSRFTOKEN=token).json()['is_favorite'])
        self.assertTrue(client.post(comparison, HTTP_X_CSRFTOKEN=token).json()['is_added'])
        self.assertContains(client.get(self.item.get_absolute_url()), 'В избранном')

    def test_form_fallback_is_furniture_styled_and_preserves_order_type(self):
        response = self.client.get(reverse('appointments:car_inquiry', args=[self.item.pk]) + '?type=order')
        self.assertContains(response, 'Изделие:')
        self.assertContains(response, 'Город / населённый пункт')
        self.assertContains(response, '?type=order')
        self.assertContains(response, 'furniture-reference.css')
        self.assertNotContains(response, 'themes/auto.css')
