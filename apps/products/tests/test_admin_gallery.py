"""Admin adapter reuses gallery services while enforcing admin permissions."""
import hashlib
import json
import tempfile
from pathlib import Path
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from apps.products.models import Product, ProductGalleryImage
from .test_gallery_upload import image_bytes


class AdminGalleryTests(TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_superuser('gallery-admin', password='test-only')
        self.client.force_login(self.user)
        self.product = Product.objects.create(title='Шкаф', slug='admin-wardrobe', price=100)
        self.change = reverse('admin:products_product_change', args=[self.product.pk])

    def url(self, action, pk=None):
        return reverse('admin:products_product_gallery_' + action, args=[pk or self.product.pk])

    def upload(self, raw):
        self.client.post(self.url('prepare'), {'action': 'hashes'})
        batch = [{'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}]
        response = self.client.post(self.url('prepare'), {'files': json.dumps(batch)})
        self.assertEqual(response.status_code, 200)
        return self.client.post(self.url('upload'), {
            'token': response.json()['token'], 'index': 0,
            'image': SimpleUploadedFile('original.jpg', raw),
        })

    def test_admin_markup_separate_forms_and_no_old_image_field(self):
        from bs4 import BeautifulSoup
        response = self.client.get(self.change)
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, 'html.parser')
        gallery = soup.select_one('#product-gallery')
        self.assertIsNone(gallery.find_parent('form'))
        self.assertIsNone(soup.select_one('#id_image'))
        self.assertIsNone(soup.select_one('#gallery-group'))
        self.assertEqual(gallery['data-upload'], self.url('upload'))
        self.assertContains(response, 'gallery-manager.js')
        response = self.client.get(reverse('admin:products_product_add'))
        self.assertContains(response, 'Сначала сохраните изделие')

    def test_upload_original_deduplicate_cover_order_delete_and_return(self):
        raw = image_bytes()
        self.assertEqual(self.upload(raw).json()['status'], 'added')
        first = self.product.gallery.get()
        self.assertEqual(Path(first.image.path).read_bytes(), raw)
        self.assertEqual(self.upload(raw).json()['status'], 'duplicate')
        self.assertEqual(self.upload(image_bytes(color='blue')).json()['status'], 'added')
        second = self.product.gallery.exclude(pk=first.pk).get()
        for action, pk, data in [('cover', second.pk, {}), ('reorder', self.product.pk,
                {f'order_{first.pk}': '9', f'order_{second.pk}': '1'})]:
            response = self.client.post(self.url(action, pk), data)
            self.assertEqual(response['Location'], self.change + '#product-gallery')
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, second.image.name)
        first.refresh_from_db()
        self.assertEqual(first.sort_order, 9)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url('delete', second.pk))
        self.assertEqual(response['Location'], self.change + '#product-gallery')
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, first.image.name)
        self.assertTrue(Path(first.image.path).exists())

    def test_saving_product_fields_does_not_replace_cover(self):
        self.upload(image_bytes())
        cover = self.product.gallery.get().image.name
        response = self.client.post(self.change, {
            'title': 'Шкаф обновлён', 'slug': self.product.slug, 'article': '',
            'price': '100', 'currency': 'RUB', 'availability_status': 'in_stock',
            'is_active': 'on', 'attributes-TOTAL_FORMS': '0',
            'attributes-INITIAL_FORMS': '0', 'attributes-MIN_NUM_FORMS': '0',
            'attributes-MAX_NUM_FORMS': '1000', '_continue': '1',
            'image-clear': 'on',  # Forged legacy input must also be ignored.
        })
        self.assertEqual(response.status_code, 302, response.context and response.context['adminform'].form.errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Шкаф обновлён')
        self.assertEqual(self.product.image.name, cover)

    def test_existing_cover_without_gallery_preserved(self):
        self.product.image.save('legacy.jpg', ContentFile(image_bytes(color='green')))
        old = self.product.image.name
        self.assertEqual(self.upload(image_bytes()).status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, old)
        self.assertContains(self.client.get(self.change), self.product.image.url)

    def test_permissions_staff_manager_readonly_and_anonymous(self):
        staff = get_user_model().objects.create_user('staff', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_product'))
        self.client.force_login(staff)
        self.assertNotContains(self.client.get(self.change), 'id="product-gallery"')
        for action in ('prepare', 'upload', 'reorder'):
            self.assertEqual(self.client.post(self.url(action)).status_code, 403)
        staff.user_permissions.add(*Permission.objects.filter(codename__in=[
            'change_product', 'add_productgalleryimage', 'change_productgalleryimage',
            'delete_productgalleryimage']))
        self.client.force_login(staff)
        self.assertEqual(self.upload(image_bytes()).status_code, 200)
        photo = self.product.gallery.get()
        staff.user_permissions.remove(Permission.objects.get(codename='delete_productgalleryimage'))
        self.client.force_login(staff)
        for action in ('cover', 'delete'):
            self.assertEqual(self.client.post(self.url(action, photo.pk)).status_code, 403)
        staff.is_staff = False
        staff.save()
        staff.profile.role = 'manager'
        staff.profile.save()
        self.assertEqual(self.client.post(self.url('prepare')).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.post(self.url('prepare')).status_code, 302)

    def test_csrf_post_only_and_token_bound_to_product(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url('prepare')).status_code, 403)
        self.assertEqual(self.client.get(self.url('reorder')).status_code, 405)
        raw = image_bytes()
        response = self.client.post(self.url('prepare'), {'files': json.dumps([
            {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}])})
        other = Product.objects.create(title='Стол', slug='other-admin', price=1)
        response = self.client.post(self.url('upload', other.pk), {
            'token': response.json()['token'], 'index': 0,
            'image': SimpleUploadedFile('photo.jpg', raw)})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(other.gallery.exists())
