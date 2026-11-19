from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.appointments.models import CallbackReferencePhoto, CallbackRequest
from apps.products.models import Category, Product
from apps.products.sitemaps import StaticSitemap
from .kitchens import KitchenRequestForm


class KitchenPageTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        setting = override_settings(MEDIA_ROOT=directory.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.url = reverse('furniture_kitchens')

    def payload(self, **overrides):
        return {'name': 'Анна', 'phone': '+7 999 123-45-67', 'layout': 'corner',
                'width_cm': '310', 'budget': 'до 400 тысяч', 'comment': 'Второй ряд 180 см', **overrides}

    def test_empty_page_has_form_links_canonical_and_one_shared_callback(self):
        response = self.client.get(self.url + '?layout=corner')
        self.assertContains(response, 'Кухни на заказ.')
        self.assertContains(response, 'id="callback"', count=1)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertEqual(response.context['kitchen_form']['layout'].value(), 'corner')
        self.assertContains(response, 'href="http://testserver/services/kitchens/"')
        self.assertEqual(list(response.context['kitchen_examples']), [])
        self.assertContains(response, 'Обсудить свою кухню')
        self.assertNotContains(response, 'Кухни, выполненные мастерской')
        self.assertIn('furniture_kitchens', StaticSitemap().items())
        self.assertEqual(self.client.head(self.url).status_code, 200)
        form = self.client.get(self.url + '?layout=invalid').context['kitchen_form']
        self.assertFalse(form['layout'].value())
        self.assertContains(self.client.get(reverse('home')), f'href="{self.url}"')
        self.assertContains(self.client.get(reverse('furniture_services')), 'Кухни на заказ — подробнее')

    def test_only_published_kitchens_with_photos_are_in_examples(self):
        kitchen = Category.objects.create(title='Кухни', slug='kuhni')
        wardrobe = Category.objects.create(title='Шкафы', slug='shkafy')
        image = BytesIO()
        Image.new('RGB', (800, 500), 'blue').save(image, 'JPEG')
        wanted = Product.objects.create(title='Кухня для примера', slug='kitchen-example', category=kitchen, price=0, image=SimpleUploadedFile('kitchen.jpg', image.getvalue(), content_type='image/jpeg'), is_active=True)
        Product.objects.create(title='Скрытая кухня', slug='hidden-kitchen', category=kitchen, price=0, image='test/hidden.jpg', is_active=False)
        Product.objects.create(title='Шкаф', slug='wardrobe', category=wardrobe, price=0, image='test/wardrobe.jpg', is_active=True)
        Product.objects.create(title='Без фото', slug='without-photo', category=kitchen, price=0, is_active=True)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['kitchen_examples']), [wanted])
        self.assertEqual(response.context['kitchen_catalog_url'], reverse('catalog:catalog') + f'?category={kitchen.pk}')
        self.assertContains(response, 'По запросу')
        self.assertNotContains(response, 'Скрытая кухня')

    @patch('apps.home.kitchens._notify_saved_inquiry')
    def test_brief_photo_saved_privately_and_refresh_does_not_repeat(self, notify):
        buffer = BytesIO()
        Image.new('RGB', (80, 60), 'blue').save(buffer, 'PNG')
        data = self.payload(reference_photo=SimpleUploadedFile('room.png', buffer.getvalue(), content_type='image/png'))
        response = self.client.post(self.url, data)
        self.assertRedirects(response, self.url + '#kitchen-request', fetch_redirect_response=False)
        inquiry = CallbackRequest.objects.get()
        self.assertIsNone(inquiry.product_id)
        self.assertEqual(inquiry.source, 'site_callback')
        for text in ['Направление: кухни на заказ', 'Угловая', '310', 'до 400 тысяч', 'Второй ряд 180 см']:
            self.assertIn(text, inquiry.comment)
        photo = CallbackReferencePhoto.objects.get(callback=inquiry)
        self.assertTrue(bytes(photo.content).startswith(b'\xff\xd8'))
        with Image.open(BytesIO(photo.content)) as image:
            self.assertEqual(image.format, 'JPEG')
        notify.assert_called_once_with(inquiry)
        self.assertContains(self.client.get(self.url), f'Заявка №{inquiry.pk} получена')
        self.assertNotContains(self.client.get(self.url), f'Заявка №{inquiry.pk} получена')
        self.assertEqual(CallbackRequest.objects.count(), 1)
        protected = self.client.get(reverse('appointments:callback_reference_photo', args=[inquiry.pk]))
        self.assertNotEqual(protected.status_code, 200)

    @patch('apps.home.kitchens._notify_saved_inquiry')
    def test_errors_keep_values_and_do_not_create_inquiry(self, notify):
        response = self.client.post(self.url, self.payload(phone='123', width_cm='-5'))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'value="Анна"', status_code=400)
        self.assertContains(response, 'aria-invalid="true"', status_code=400)
        self.assertFalse(CallbackRequest.objects.exists())
        bad = self.client.post(self.url, self.payload(reference_photo=SimpleUploadedFile('bad.jpg', b'<html>bad</html>')))
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(CallbackRequest.objects.exists())
        form = KitchenRequestForm(self.payload(layout='invalid'))
        self.assertFalse(form.is_valid())
        self.assertIn('layout', form.errors)
        notify.assert_not_called()

    @patch('apps.home.kitchens._notify_saved_inquiry')
    def test_minimum_fields_honeypot_and_csrf(self, notify):
        response = self.client.post(self.url, {'name': 'Анна', 'phone': '+79991234567'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CallbackRequest.objects.count(), 1)
        self.assertIn('кухни на заказ', CallbackRequest.objects.get().comment)
        response = self.client.post(self.url, self.payload(website='spam'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CallbackRequest.objects.count(), 1)
        self.assertEqual(notify.call_count, 1)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, self.payload()).status_code, 403)

    @patch('apps.home.kitchens._notify_saved_inquiry')
    def test_attachment_failure_rolls_back_inquiry(self, notify):
        buffer = BytesIO()
        Image.new('RGB', (60, 40), 'green').save(buffer, 'PNG')
        with patch('apps.home.kitchens.CallbackReferencePhoto.objects.create', side_effect=OSError('failure')):
            with self.assertRaises(OSError):
                self.client.post(self.url, self.payload(reference_photo=SimpleUploadedFile('room.png', buffer.getvalue())))
        self.assertFalse(CallbackRequest.objects.exists())
        notify.assert_not_called()
