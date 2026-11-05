"""шаг 19: public brand furniture, SEO, privacy and action contracts."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from apps.products.models import Brand, Product
from apps.wishlist.models import Favorite


class FurnitureBrandPageTests(TestCase):
    def setUp(self):
        from apps.products.tests.image_fixtures import image_test_storage
        image_test_storage(self, ['brands/original-logo.png', 'products/original-brand-case.jpg'])
        self.brand=Brand.objects.create(name='Мебельная мастерская',slug='furniture-workshop',country='Россия',description='Описание мастерской\n\nВторая строка',meta_title='Мебель мастерской',meta_description='Индивидуальная мебель',logo='brands/original-logo.png')
        self.product=Product.objects.create(title='Шкаф из дуба',slug='brand-oak-case',brand=self.brand,price=120000,currency='EUR',image='products/original-brand-case.jpg')
        self.hidden=Product.objects.create(title='Скрытый проект',slug='private-brand-case',brand=self.brand,price=1,is_active=False)
        self.other=Product.objects.create(title='Другой бренд',slug='other-brand-case',price=1)
        self.url=self.brand.get_absolute_url()

    def test_furniture_shell_seo_original_files_and_published_selection(self):
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        for text in ['furniture-brand-page.css','Изделия бренда','Мебель мастерской','Индивидуальная мебель','/media/brands/original-logo.png','/media/products/original-brand-case.jpg','120\u00a0000 €','Страна: Россия','Описание мастерской','width=device-width']:
            self.assertContains(response,text)
        for text in [self.hidden.title,self.hidden.slug,self.other.title,'автомобил','themes/auto.css','/thumbs/']:
            self.assertNotContains(response,text)
        self.assertEqual([p.pk for p in response.context['products']],[self.product.pk])
        self.assertContains(response,'property="og:title" content="Мебель мастерской"')
        self.assertContains(response,'name="description" content="Индивидуальная мебель"')

    def test_empty_brand_has_actionable_fallback(self):
        self.product.is_active=False;self.product.save(update_fields=['is_active'])
        response=self.client.get(self.url)
        self.assertContains(response,'Опубликованных изделий этого бренда пока нет')
        self.assertContains(response,'href="/#callback"')
        self.assertNotContains(response,self.product.title)
        self.assertEqual(Product.objects.filter(brand=self.brand).count(),2)

    def test_meta_description_kept_without_body_description_and_fallbacks(self):
        self.brand.description='';self.brand.save(update_fields=['description'])
        self.assertContains(self.client.get(self.url),'name="description" content="Индивидуальная мебель"')
        self.brand.meta_title='';self.brand.meta_description='';self.brand.description='Дерево и мебель';self.brand.logo='';self.brand.country=''
        self.brand.save()
        response=self.client.get(self.url)
        self.assertContains(response,'name="description" content="Дерево и мебель"')
        self.assertNotContains(response,'fbp-logo" src=')
        self.assertNotContains(response,'Страна:')

    def test_guest_and_account_favorites_state(self):
        session=self.client.session;session['wishlist']=[self.product.pk];session.save()
        self.assertContains(self.client.get(self.url),'wishlist-btn active')
        user=get_user_model().objects.create_user('brand-page-client',password='test-only')
        Favorite.objects.create(user=user,product=self.product)
        self.client.force_login(user)
        self.assertContains(self.client.get(self.url),'wishlist-btn active')

    def test_direct_brand_page_csrf_supports_favorites_and_comparison(self):
        client=Client(enforce_csrf_checks=True);client.get(self.url)
        token=client.cookies['csrftoken'].value
        for url in [reverse('wishlist:toggle',args=[self.product.pk]),reverse('catalog:toggle_comparison_ajax',args=[self.product.pk])]:
            self.assertEqual(client.post(url).status_code,403)
            self.assertEqual(client.post(url,HTTP_X_CSRFTOKEN=token).status_code,200)
        response=client.get(self.url)
        self.assertContains(response,'wishlist-btn active')
        self.assertContains(response,'compare-btn active')

    def test_brand_fields_are_escaped_and_get_keeps_data(self):
        self.brand.name='<script>brand()</script>';self.brand.description='<img src=x onerror=alert(1)>';self.brand.save()
        response=self.client.get(self.url)
        self.assertNotContains(response,self.brand.name)
        self.assertNotContains(response,self.brand.description)
        self.assertContains(response,'&lt;script&gt;brand()&lt;/script&gt;')
        self.product.refresh_from_db();self.assertEqual(self.product.brand_id,self.brand.pk)
        self.assertEqual(Product.objects.count(),3)

    def test_unknown_brand_is_404_and_existing_url_unchanged(self):
        self.assertEqual(self.url,reverse('catalog:brand_detail',kwargs={'slug':self.brand.slug}))
        self.assertEqual(self.client.get(reverse('catalog:brand_detail',kwargs={'slug':'missing-brand'})).status_code,404)
