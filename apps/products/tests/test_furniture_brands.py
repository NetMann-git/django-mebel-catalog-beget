"""шаг 18: brand manager keeps IDs, links, ordering and media contracts."""
from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from apps.products.models import Brand, Product, CarModel
from apps.users.constants import ROLE_MANAGER


class FurnitureBrandPagesTests(TestCase):
    def setUp(self):
        user=get_user_model().objects.create_user('brand-manager',password='test-only')
        user.profile.role=ROLE_MANAGER;user.profile.save()
        self.client.force_login(user)
        self.brand=Brand.objects.create(name='Мастерская',slug='workshop',country='Россия',sort_order=3)
        self.other=Brand.objects.create(name='Другой бренд',slug='other-brand',country='Италия',sort_order=10)
        self.product=Product.objects.create(title='Стол',slug='table-brand',brand=self.brand,price=100)
        self.url=reverse('catalog:brand_list_manage')

    def data(self,**changes):
        data={'name':self.brand.name,'slug':self.brand.slug,'country':'Россия','sort_order':3,'description':'Описание','meta_title':'Заголовок','meta_description':'Для поиска'}
        data.update(changes);return data

    def test_pages_use_furniture_shell_and_get_preserves_data(self):
        for name,args in [('brand_list_manage',[]),('brand_create',[]),('brand_edit',[self.brand.pk]),('brand_delete',[self.brand.pk])]:
            response=self.client.get(reverse('catalog:'+name,args=args))
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'furniture-brands.css')
            self.assertContains(response,'width=device-width')
            self.assertNotContains(response,'themes/auto.css')
        self.assertEqual(Brand.objects.count(),2)
        self.product.refresh_from_db();self.assertEqual(self.product.brand_id,self.brand.pk)

    def test_search_and_filtered_order_save_preserve_other_brands(self):
        response=self.client.get(self.url,{'search':'Россия'})
        self.assertEqual(list(response.context['brands']),[self.brand])
        self.assertContains(response,f'name="sort_order_{self.brand.pk}"')
        self.assertNotContains(response,f'name="sort_order_{self.other.pk}"')
        self.client.post(self.url+'?search=Россия',{f'sort_order_{self.brand.pk}':12,f'sort_order_{self.other.pk}':0})
        self.brand.refresh_from_db();self.other.refresh_from_db()
        self.assertEqual((self.brand.sort_order,self.other.sort_order),(12,10))
        self.assertContains(self.client.get(self.url,{'search':'не существует'}),'Брендов по запросу не найдено')

    def test_create_and_edit_preserve_id_product_link_url_and_metadata(self):
        response=self.client.post(reverse('catalog:brand_create'),self.data(name='Новая мастерская',slug=''))
        created=Brand.objects.get(name='Новая мастерская')
        self.assertEqual(response.status_code,302)
        self.assertTrue(created.slug.isascii())
        self.client.post(reverse('catalog:brand_edit',args=[self.brand.pk]),self.data(name='Мастерская обновлена'))
        self.brand.refresh_from_db();self.product.refresh_from_db()
        self.assertEqual(self.brand.slug,'workshop')
        self.assertEqual(self.product.brand_id,self.brand.pk)
        self.assertEqual(self.brand.meta_title,'Заголовок')
        self.assertEqual(Brand.objects.count(),3)

    def test_invalid_form_does_not_change_record(self):
        response=self.client.post(reverse('catalog:brand_edit',args=[self.brand.pk]),self.data(name=self.other.name,sort_order=-1))
        self.assertTrue(response.context['form'].errors)
        self.brand.refresh_from_db();self.assertEqual(self.brand.name,'Мастерская')

    def test_logo_upload_keeps_original_bytes_and_form_supports_files(self):
        with TemporaryDirectory() as folder,self.settings(MEDIA_ROOT=folder):
            data=BytesIO();Image.new('RGB',(30,20),'green').save(data,format='PNG');original=data.getvalue()
            upload=SimpleUploadedFile('brand.png',original,content_type='image/png')
            self.client.post(reverse('catalog:brand_edit',args=[self.brand.pk]),self.data(logo=upload))
            self.brand.refresh_from_db()
            with self.brand.logo.open('rb') as file:self.assertEqual(file.read(),original)
            response=self.client.get(reverse('catalog:brand_edit',args=[self.brand.pk]))
            self.assertContains(response,'enctype="multipart/form-data"')
            self.assertContains(response,self.brand.logo.url)
            self.assertContains(self.client.get(self.url),self.brand.logo.url)
            self.assertNotContains(self.client.get(self.url),'/thumbs/')

    def test_delete_only_post_preserves_products_and_protected_models(self):
        url=reverse('catalog:brand_delete',args=[self.brand.pk])
        self.assertContains(self.client.get(url),'Подтвердить удаление')
        model=CarModel.objects.create(brand=self.brand,name='Существующая модель',slug='existing-brand-model')
        self.client.post(url)
        self.assertTrue(Brand.objects.filter(pk=self.brand.pk).exists())
        self.assertTrue(CarModel.objects.filter(pk=model.pk).exists())
        empty_url=reverse('catalog:brand_delete',args=[self.other.pk])
        second_product=Product.objects.create(title='Полка',slug='other-brand-shelf',brand=self.other,price=50)
        self.client.post(empty_url)
        second_product.refresh_from_db();self.assertIsNone(second_product.brand_id)
        self.assertTrue(Product.objects.filter(pk=second_product.pk).exists())

    def test_customer_staff_and_guest_cannot_read_or_mutate(self):
        customer=get_user_model().objects.create_user('brand-customer',password='test-only',is_staff=True)
        for user in [customer,None]:
            if user:self.client.force_login(user)
            else:self.client.logout()
            for name,args in [('brand_list_manage',[]),('brand_create',[]),('brand_edit',[self.brand.pk]),('brand_delete',[self.brand.pk])]:
                url=reverse('catalog:'+name,args=args)
                self.assertEqual(self.client.get(url).status_code,302)
                self.assertEqual(self.client.post(url,self.data()).status_code,302)
        self.assertEqual(Brand.objects.count(),2)

    def test_csrf_and_escaped_search(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(get_user_model().objects.get(username='brand-manager'))
        for name,args in [('brand_list_manage',[]),('brand_create',[]),('brand_edit',[self.brand.pk]),('brand_delete',[self.brand.pk])]:
            self.assertEqual(strict.post(reverse('catalog:'+name,args=args),self.data()).status_code,403)
        payload='<script>alert(1)</script>'
        response=self.client.get(self.url,{'search':payload})
        self.assertNotContains(response,payload)
        self.assertContains(response,'&lt;script&gt;alert(1)&lt;/script&gt;')
