from io import BytesIO
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from PIL import Image
from apps.products.models import Product, Category
from .models import CallbackRequest, CallbackReferencePhoto


class EstimateRequestTests(TestCase):
    def setUp(self):
        self.url = reverse('furniture_request')
        self.category = Category.objects.create(title='Кухни', slug='kuhni')
        self.product = Product.objects.create(title='Кухня по размерам', slug='estimate-kitchen', price=0, category=self.category)
        self.data = {'name':'Анна', 'phone':'+79991234567', 'direction':'kuhni', 'layout':'corner', 'width_cm':'320', 'budget':'до 400 тысяч', 'comment':'Нужен остров'}

    def photo(self):
        b = BytesIO(); Image.new('RGB', (90, 60), 'blue').save(b, 'PNG')
        return SimpleUploadedFile('room.png', b.getvalue(), content_type='image/png')

    def test_context_prefill_and_hidden_or_invalid_product(self):
        response = self.client.get(self.url, {'product':self.product.pk})
        self.assertContains(response, self.product.title)
        self.assertEqual(response.context['estimate_form']['direction'].value(), 'kuhni')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'noindex, follow')
        self.assertEqual(response['Cache-Control'].find('no-store') >= 0, True)
        self.product.is_active = False; self.product.save()
        self.assertEqual(self.client.get(self.url, {'product':self.product.pk}).status_code, 404)
        for value in ('999999', '-1', 'abc', '9999999999999999999999999999'):
            self.assertEqual(self.client.get(self.url, {'product':value}).status_code, 404)

    @patch('apps.appointments.estimate_views._notify_saved_inquiry')
    def test_generic_request_photo_details_and_refresh(self, notify):
        response = self.client.post(self.url, {**self.data, 'reference_photo':self.photo()})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        inquiry = CallbackRequest.objects.get()
        self.assertIsNone(inquiry.product_id)
        self.assertEqual(inquiry.source, 'site_callback')
        for value in ['кухни на заказ', 'Угловая', '320 см', 'до 400 тысяч', 'Нужен остров']:
            self.assertIn(value, inquiry.comment)
        self.assertTrue(bytes(inquiry.reference_photo.content).startswith(b'\xff\xd8'))
        notify.assert_called_once_with(inquiry)
        self.assertContains(self.client.get(self.url), f'Заявка №{inquiry.pk} получена')
        self.assertNotContains(self.client.get(self.url), f'Заявка №{inquiry.pk} получена')
        self.assertEqual(CallbackRequest.objects.count(), 1)
        self.assertNotEqual(self.client.get(reverse('appointments:callback_reference_photo', args=[inquiry.pk])).status_code, 200)

    @patch('apps.appointments.estimate_views._notify_saved_inquiry')
    def test_product_purposes_keep_context_and_ignore_forged_body_product(self, notify):
        for purpose, source in [('similar','similar_project'),('order','product_order'),('detail','product_detail')]:
            response = self.client.post(self.url + f'?product={self.product.pk}&purpose={purpose}', {**self.data, 'product':'999999'})
            self.assertEqual(response.status_code, 302)
            inquiry = CallbackRequest.objects.latest('pk')
            self.assertEqual(inquiry.product, self.product)
            self.assertEqual(inquiry.source, source)
        self.assertEqual(notify.call_count, 3)

    @patch('apps.appointments.estimate_views._notify_saved_inquiry')
    def test_invalid_inputs_preserved_no_orphans_and_minimal_submission(self, notify):
        for extra in ({'phone':'123'}, {'width_cm':'-1'}, {'direction':'wrong'}, {'reference_photo':SimpleUploadedFile('bad.jpg', b'bad')}):
            response = self.client.post(self.url, {**self.data, **extra})
            self.assertEqual(response.status_code, 400)
            self.assertContains(response, 'value="Анна"', status_code=400)
        self.assertFalse(CallbackRequest.objects.exists())
        self.assertFalse(CallbackReferencePhoto.objects.exists())
        notify.assert_not_called()
        self.assertEqual(self.client.post(self.url, {'name':'Анна','phone':'+79991234567'}).status_code, 302)
        self.assertEqual(CallbackRequest.objects.count(), 1)

    @patch('apps.appointments.estimate_views._notify_saved_inquiry')
    def test_private_attachment_write_failure_rolls_back_and_honeypot_csrf(self, notify):
        with patch('apps.appointments.estimate_service.CallbackReferencePhoto.objects.create', side_effect=OSError('failure')):
            with self.assertRaises(OSError):
                self.client.post(self.url, {**self.data, 'reference_photo':self.photo()})
        self.assertFalse(CallbackRequest.objects.exists())
        self.client.post(self.url, {**self.data, 'website':'spam'})
        self.assertFalse(CallbackRequest.objects.exists())
        notify.assert_not_called()
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, self.data).status_code, 403)

    @patch('apps.appointments.views._notify_saved_inquiry')
    def test_quick_callback_from_estimate_page_keeps_product(self, notify):
        self.client.post(reverse('appointments:callback_submit'), {'name':'Анна','phone':'+79991234567', 'return_to':self.url+f'?product=999999&product={self.product.pk}'})
        self.assertEqual(CallbackRequest.objects.get().product, self.product)
