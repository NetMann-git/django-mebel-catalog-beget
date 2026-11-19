import json
from decimal import Decimal
from io import StringIO, BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse

from apps.appointments.models import CallbackRequest, CallbackReferencePhoto, WorkshopOrder
from apps.products.models import Category, Product
from apps.products.tests.image_fixtures import image_test_storage
from .copy_registry import PAGES
from .models import ClientShowcase, ContactSettings, EditablePage, TeamMember


class LaunchAuditTests(TestCase):
    def run_audit(self, **kwargs):
        with TemporaryDirectory() as folder:
            target = Path(folder) / 'report.json'
            error = None
            try:
                call_command('audit_furniture_launch', output=str(target), stdout=StringIO(), **kwargs)
            except CommandError as exc:
                error = exc
            return json.loads(target.read_text()), error

    def test_default_data_pages_assets_and_permissions_without_business_writes(self):
        counts = {model: model.objects.count() for model in (CallbackRequest, WorkshopOrder, EditablePage, ClientShowcase, TeamMember)}
        report, error = self.run_audit()
        self.assertIsNone(error, [row for row in report['checks'] if row['status'] == 'error'])
        self.assertGreater(len(report['checks']), 90)
        for model, count in counts.items():
            self.assertEqual(model.objects.count(), count)
        self.assertFalse(EditablePage.objects.exists())

    def test_missing_media_contacts_draft_and_legacy_video_are_reported(self):
        image_test_storage(self, [])
        product = Product.objects.create(title='Шкаф', slug='missing-cover', price=0, image='products/lost.jpg')
        ContactSettings.objects.filter(pk=1).update(is_published=False)
        EditablePage.objects.create(key='about', draft={'heading': 'Новый текст'})
        video = ClientShowcase.objects.create(name='Видео', vehicle='Кухня', show_video_on_home=True, rutube_url='https://example.test/video')
        report, error = self.run_audit()
        self.assertIsNotNone(error)
        errors = {row['check'] for row in report['checks'] if row['status'] == 'error'}
        self.assertIn(f'media.products.{product.pk}.image', errors)
        self.assertIn(f'video.{video.pk}', errors)
        self.assertIn('contacts', errors)
        self.assertIn('drafts', {row['check'] for row in report['checks'] if row['status'] == 'warning'})
        self.assertNotIn('example.test', json.dumps(report))

    def test_pending_migrations_stop_page_checks_and_deployment_reports_no_secret(self):
        with patch('apps.home.management.commands.audit_furniture_launch.MigrationExecutor') as executor:
            executor.return_value.migration_plan.return_value = [object()]
            report, error = self.run_audit(deployment=True)
        self.assertIsNotNone(error)
        self.assertFalse(any(row['check'].startswith('page.') for row in report['checks']))
        self.assertNotIn(connection.settings_dict.get('PASSWORD') or 'no-real-password', json.dumps(report))


class HomePublicationSafetyTests(TestCase):
    def test_video_is_explicitly_enabled_valid_and_gated_by_cookie_consent(self):
        url = 'https://rutube.ru/play/embed/0123456789abcdef0123456789abcdef/'
        legacy = ClientShowcase.objects.create(name='Старое авто', vehicle='Авто', rutube_url=url)
        self.assertNotContains(self.client.get('/'), url)
        legacy.show_video_on_home = True
        legacy.vehicle = 'Кухня'
        legacy.save()
        response = self.client.get('/')
        self.assertContains(response, f'data-consent-src="{url}"')
        self.assertNotContains(response, f' src="{url}"')
        legacy.is_published = False
        legacy.save()
        self.assertNotContains(self.client.get('/'), url)

    def test_all_content_mutations_reject_external_returns_but_keep_local_filters(self):
        user = get_user_model().objects.create_user('return-manager')
        user.profile.role = 'manager'
        user.profile.save()
        self.client.force_login(user)
        for prefix, model, argument in [('client', ClientShowcase, 'client_id'), ('team', TeamMember, 'member_id')]:
            item = model.objects.create(name='Тест', **({'vehicle':'Шкаф'} if prefix == 'client' else {'position':'Мастер'}))
            fallback = reverse(f'home:{prefix}_list_manage')
            for target in ['https://example.test/', '//example.test/', '/\\example.test/', 'javascript:alert(1)']:
                response = self.client.post(reverse(f'home:{prefix}_toggle_published', kwargs={argument:item.pk}), {'next':target})
                self.assertEqual(response['Location'], fallback)
            response = self.client.post(reverse(f'home:{prefix}_toggle_published', kwargs={argument:item.pk}), {'next':fallback+'?status=hidden&page=2'})
            self.assertEqual(response['Location'], fallback+'?status=hidden&page=2')
            self.assertEqual(self.client.get(reverse(f'home:{prefix}_toggle_published', kwargs={argument:item.pk})).status_code, 405)


class FurnitureJourneyTests(TestCase):
    @patch('apps.appointments.estimate_views._notify_saved_inquiry')
    def test_catalog_estimate_private_photo_order_payment_and_page_publication(self, notify):
        image_test_storage(self, ['products/journey.jpg'])
        category = Category.objects.create(title='Кухни', slug='kuhni')
        product = Product.objects.create(title='Кухня по размерам', slug='journey-kitchen', category=category, image='products/journey.jpg', price=0)
        self.assertContains(self.client.get(reverse('catalog:catalog')), product.title)
        self.assertContains(self.client.get(product.get_absolute_url()), product.title)
        request_url = reverse('furniture_request') + f'?product={product.pk}&purpose=similar'
        self.assertContains(self.client.get(request_url), product.title)
        buffer = BytesIO()
        Image.new('RGB', (90, 60), 'blue').save(buffer, 'PNG')
        response = self.client.post(request_url, {'name':'Анна', 'phone':'+79991234567', 'direction':'kuhni', 'layout':'corner', 'width_cm':'320', 'comment':'Нужен остров', 'reference_photo':SimpleUploadedFile('room.png', buffer.getvalue(), content_type='image/png')})
        self.assertEqual(response.status_code, 302)
        inquiry = CallbackRequest.objects.get()
        self.assertEqual(inquiry.product, product)
        self.assertEqual(inquiry.source, 'similar_project')
        self.assertEqual(CallbackReferencePhoto.objects.count(), 1)
        notify.assert_called_once_with(inquiry)
        photo_url = reverse('appointments:callback_reference_photo', args=[inquiry.pk])
        self.assertNotEqual(self.client.get(photo_url).status_code, 200)
        manager = get_user_model().objects.create_user('journey-manager')
        manager.profile.role = 'manager'
        manager.profile.save()
        self.client.force_login(manager)
        self.assertEqual(self.client.get(photo_url).status_code, 200)
        create = reverse('appointments:order_from_inquiry', args=[inquiry.pk])
        self.assertEqual(self.client.post(create).status_code, 302)
        self.client.post(create)
        self.assertEqual(WorkshopOrder.objects.count(), 1)
        order = WorkshopOrder.objects.get()
        payload = {'title':order.title, 'client_name':order.client_name, 'phone':order.phone, 'email':'', 'city':'', 'specification':order.specification, 'stage':'production', 'responsible':manager.pk, 'due_on':'', 'agreed_total':'350000', 'paid':'100000', 'note':'', 'revision':order.revision}
        self.assertEqual(self.client.post(reverse('appointments:order_detail', args=[order.pk]), payload).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.balance, Decimal('250000'))
        self.assertEqual(order.events.count(), 2)
        data = {name:field['default'] for name, field in PAGES['home']['fields'].items()}
        data.update(revision=0, action='save', heading='Мебель для вашего дома')
        editor = reverse('home:copy_edit', args=['home'])
        self.assertEqual(self.client.post(editor, data).status_code, 302)
        public = Client()
        self.assertNotContains(public.get('/'), data['heading'])
        self.assertContains(self.client.get(reverse('home:copy_preview', args=['home'])), data['heading'])
        self.assertContains(self.client.get(editor), 'Отменить')
        data.update(revision=1, action='publish')
        self.assertEqual(self.client.post(editor, data).status_code, 302)
        self.assertContains(public.get('/'), data['heading'])
        self.assertNotEqual(public.get(photo_url).status_code, 200)
        self.assertNotEqual(public.get(reverse('appointments:order_detail', args=[order.pk])).status_code, 200)
