"""Management listing: private records, safe search and unchanged actions."""
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.products.models import Category, Product
from .test_gallery_upload import image_bytes


class FurnitureManageListTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('furniture-manager')
        self.user.profile.role = 'manager'
        self.user.profile.save()
        self.client.force_login(self.user)
        self.url = reverse('catalog:product_list_manage')
        self.category = Category.objects.create(title='Шкафы', slug='wardrobes')
        self.published = Product.objects.create(title='Шкаф для прихожей', slug='hall-wardrobe',
            price='120000.50', currency='RUB', article='ME-001', category=self.category)
        self.draft = Product.objects.create(title='Скрытый проект кухни', slug='private-kitchen',
            price='100', currency='EUR', article='ME-002', is_active=False)

    def test_private_listing_links_publication_and_currency(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LUSTRID.RU')
        self.assertContains(response, 'Управление изделиями')
        self.assertContains(response, self.draft.title)
        self.assertContains(response, 'noindex, nofollow')
        soup = BeautifulSoup(response.content, 'html.parser')
        rows = soup.select('tbody tr')
        draft = next(row for row in rows if self.draft.title in row.get_text())
        active = next(row for row in rows if self.published.title in row.get_text())
        self.assertIn('Не опубликовано', draft.get_text())
        self.assertIn('100 EUR', draft.get_text(' ', strip=True))
        self.assertIsNone(draft.select_one('[aria-label^="Посмотреть на сайте:"]'))
        self.assertEqual(active.select_one('[aria-label^="Посмотреть на сайте:"]')['href'],
                         self.published.get_absolute_url())
        self.assertIn('120\xa0000,5 RUB', active.get_text(' ', strip=True))
        self.assertEqual(draft.select_one('.fm-manage__name a')['href'],
                         reverse('catalog:product_edit', args=[self.draft.pk]))
        self.assertContains(response, reverse('catalog:product_delete', args=[self.draft.pk]))

    def test_search_title_article_category_and_empty_reset(self):
        for term in ('прихожей', 'ME-001', 'Шкафы'):
            response = self.client.get(self.url, {'search': term})
            self.assertContains(response, self.published.title)
            self.assertNotContains(response, self.draft.title)
            self.assertEqual(response.context['total'], 1)
        response = self.client.get(self.url, {'search': 'нет совпадений'})
        self.assertContains(response, 'Изделия не найдены')
        self.assertContains(response, 'Сбросить поиск')

    def test_search_special_characters_survive_pagination(self):
        term = 'Шкаф + кухня &page=999 "полка"'
        Product.objects.bulk_create([Product(title=f'{term} {i}', slug=f'quoted-{i}', price=1)
                                    for i in range(23)])
        response = self.client.get(self.url, {'search': term})
        self.assertEqual(len(response.context['products']), 20)
        soup = BeautifulSoup(response.content, 'html.parser')
        link = soup.select_one('[aria-label="Следующая страница"]')['href']
        query = parse_qs(urlparse(link).query)
        self.assertEqual(query, {'page': ['2'], 'search': [term]})
        response = self.client.get(self.url + link)
        self.assertEqual(response.context['search'], term)
        self.assertEqual(len(response.context['products']), 3)
        self.assertEqual(response.context['total'], 23)
        self.assertEqual(self.client.get(self.url, {'page': 'bad'}).status_code, 200)

    def test_permissions_do_not_leak_drafts(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertNotContains(response, self.draft.title, status_code=302)
        user = get_user_model().objects.create_user('ordinary')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertNotContains(response, self.draft.title, status_code=302)
        user = get_user_model().objects.create_superuser('super', password='test-only')
        self.client.force_login(user)
        self.assertContains(self.client.get(self.url), self.draft.title)

    def test_images_get_and_confirmation_do_not_change_records_or_originals(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            raw = image_bytes()
            self.published.image.save('original.jpg', ContentFile(raw))
            name = self.published.image.name
            original = Path(self.published.image.path)
            before = list(Product.objects.order_by('pk').values())
            response = self.client.get(self.url)
            image = BeautifulSoup(response.content, 'html.parser').select_one('.fm-manage__photo img')
            self.assertNotEqual(image['src'], self.published.image.url)
            thumbnail_name = urlparse(image['src']).path.removeprefix('/media/')
            self.assertTrue((Path(folder) / thumbnail_name).is_file())
            self.assertContains(response, 'Нет фото')
            confirm = self.client.get(reverse('catalog:product_delete', args=[self.published.pk]))
            self.assertEqual(confirm.status_code, 200)
            self.assertEqual(list(Product.objects.order_by('pk').values()), before)
            self.assertEqual(original.read_bytes(), raw)
            self.assertCountEqual([str(p.relative_to(folder)) for p in Path(folder).rglob('*') if p.is_file()], [name, thumbnail_name])

    def test_untrusted_titles_and_queries_are_escaped(self):
        text = '<script>alert("x")</script>'
        self.published.title = text
        self.published.save(update_fields=['title'])
        response = self.client.get(self.url, {'search': text})
        self.assertNotContains(response, text)
        self.assertContains(response, '&lt;script&gt;')
