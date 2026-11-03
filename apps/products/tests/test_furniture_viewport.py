"""шаг 20: template inheritance must retain exactly one mobile viewport."""
from html.parser import HTMLParser
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.products.models import Brand, Product, Category, AttributeType, AttributeValue


class HeadMetadata(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_head = False
        self.metadata = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.in_head = True
        if tag == 'meta' and self.in_head:
            self.metadata.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False


class FurnitureViewportTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name='Мастерская', slug='viewport-brand', meta_title='Бренд для поиска', meta_description='Описание бренда для поиска')
        self.product = Product.objects.create(title='Шкаф', slug='viewport-product', price=100, brand=self.brand, meta_title='Изделие для поиска', meta_description='Описание изделия для поиска')
        self.category = Category.objects.create(title='Шкафы', slug='viewport-category')
        self.kind = AttributeType.objects.create(name='Материал', slug='viewport-material', data_type='choice')
        self.value = AttributeValue.objects.create(attribute_type=self.kind, value='Дуб')

    def assert_viewport(self, response):
        self.assertEqual(response.status_code, 200)
        metadata = HeadMetadata(response.content.decode()).metadata
        viewport = [meta for meta in metadata if meta.get('name') == 'viewport']
        self.assertEqual(len(viewport), 1)
        self.assertEqual(viewport[0]['content'], 'width=device-width, initial-scale=1')
        return metadata

    def test_public_pages_and_auth_pages_retain_viewport_and_custom_seo(self):
        urls = [reverse('home'), reverse('catalog:catalog'), self.product.get_absolute_url(), self.brand.get_absolute_url(),
                reverse('wishlist:list'), reverse('catalog:comparison'), reverse('catalog:recently_viewed'),
                reverse('appointments:car_inquiry', args=[self.product.pk]), reverse('users:login')]
        for url in urls:
            with self.subTest(url=url):
                self.assert_viewport(self.client.get(url))
        for url, description in [(self.product.get_absolute_url(), self.product.meta_description), (self.brand.get_absolute_url(), self.brand.meta_description)]:
            metadata = self.assert_viewport(self.client.get(url))
            self.assertIn({'name': 'description', 'content': description}, metadata)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Brand.objects.count(), 1)

    def test_manager_inheritance_retains_noindex_and_single_viewport(self):
        user = get_user_model().objects.create_superuser('viewport-admin', password='test-only')
        self.client.force_login(user)
        urls = [reverse('users:manager_dashboard'), reverse('catalog:product_list_manage'),
                reverse('catalog:product_edit', args=[self.product.pk]),
                reverse('catalog:category_list_manage'), reverse('catalog:category_edit', args=[self.category.pk]),
                reverse('catalog:attribute_type_list_manage'), reverse('catalog:attribute_type_edit', args=[self.kind.pk]),
                reverse('catalog:attribute_value_edit', args=[self.kind.pk, self.value.pk]),
                reverse('catalog:product_attributes', args=[self.product.pk]),
                reverse('catalog:brand_list_manage'), reverse('catalog:brand_edit', args=[self.brand.pk]),
                reverse('recommendations:manage'), reverse('recommendations:add'),
                reverse('appointments:callback_request_list')]
        for url in urls:
            with self.subTest(url=url):
                metadata = self.assert_viewport(self.client.get(url))
                # The existing product editor inherits public SEO metadata;
                # this viewport-only patch must not invent a new robots policy.
                if url != reverse('catalog:product_edit', args=[self.product.pk]):
                    self.assertIn({'name': 'robots', 'content': 'noindex, nofollow'}, metadata)
