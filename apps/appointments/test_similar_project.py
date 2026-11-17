from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.products.models import Product

from .models import CallbackRequest


class SimilarProjectTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='Шкаф по размерам', slug='reference-wardrobe', price=90000)
        self.url = reverse('appointments:car_inquiry', args=[self.product.pk]) + '?type=similar'
        self.fields = {'name': 'Анна', 'city': 'Ростов-на-Дону', 'phone': '+79991234567', 'comment': 'Ширина 180 см'}

    @patch('apps.appointments.views._notify_saved_inquiry')
    def test_customer_submits_photo_and_manager_can_download_it(self, notify):
        self.assertContains(self.client.get(self.product.get_absolute_url()), self.url)
        self.assertContains(self.client.get(self.url), 'enctype="multipart/form-data"')
        image = BytesIO()
        Image.new('RGB', (1800, 900), 'brown').save(image, 'PNG')
        response = self.client.post(self.url, {
            **self.fields,
            'reference_photo': SimpleUploadedFile('room.png', image.getvalue(), content_type='image/png'),
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['success'])
        inquiry = CallbackRequest.objects.get(source='similar_project')
        self.assertEqual(inquiry.product, self.product)
        self.assertEqual(inquiry.comment, 'Ширина 180 см')
        notify.assert_called_once_with(inquiry)

        photo_url = reverse('appointments:callback_reference_photo', args=[inquiry.pk])
        self.assertEqual(self.client.get(photo_url).status_code, 302)
        self.client.force_login(get_user_model().objects.create_user('external-customer'))
        self.assertEqual(self.client.get(photo_url).status_code, 302)
        manager = get_user_model().objects.create_user('photo-manager')
        manager.profile.role = 'manager'
        manager.profile.save(update_fields=['role'])
        self.client.force_login(manager)
        inbox = self.client.get(reverse('appointments:callback_request_list'))
        self.assertContains(inbox, photo_url)
        photo = self.client.get(photo_url)
        self.assertEqual(photo['Content-Type'], 'image/jpeg')
        self.assertIn('no-store', photo['Cache-Control'])
        self.assertTrue(photo['Content-Disposition'].startswith('attachment'))
        with Image.open(BytesIO(photo.content)) as saved:
            self.assertEqual(saved.size, (1600, 800))
            self.assertEqual(saved.format, 'JPEG')

    @patch('apps.appointments.views._notify_saved_inquiry')
    def test_bad_file_creates_no_request_and_photo_is_optional(self, notify):
        invalid = self.client.post(self.url, {
            **self.fields,
            'reference_photo': SimpleUploadedFile('bad.jpg', b'<html>not an image</html>'),
        })
        self.assertContains(invalid, 'Загрузите обычное фото', status_code=400)
        self.assertFalse(CallbackRequest.objects.exists())
        notify.assert_not_called()

        response = self.client.post(self.url, self.fields, follow=True)
        inquiry = CallbackRequest.objects.get(source='similar_project')
        self.assertContains(response, f'Номер заявки: <strong>#{inquiry.pk}</strong>')
        self.assertFalse(hasattr(inquiry, 'reference_photo'))
