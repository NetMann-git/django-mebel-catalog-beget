"""шаг 17: furniture manager actions, rights and scheduling contracts."""
import re
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.products.models import Product
from apps.users.constants import ROLE_MANAGER, ROLE_ADMIN
from .forms import PromotedProductForm
from .models import PromotedProduct
from .services import RecommendationService


class FurnitureRecommendationsTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user('manager', password='test-only')
        self.manager.profile.role = ROLE_MANAGER
        self.manager.profile.save()
        self.product = Product.objects.create(title='Шкаф из дуба', slug='oak-promotion', price=100, image='products/original-promotion.jpg')
        self.promo = PromotedProduct.objects.create(product=self.product, page='wishlist', priority=10)
        self.url = reverse('recommendations:manage')
        self.client.force_login(self.manager)

    def payload(self, **changes):
        data = {'product': self.product.pk, 'page': 'wishlist', 'priority': 12, 'is_active': 'on', 'start_date': '', 'end_date': ''}
        data.update(changes)
        return data

    def test_furniture_pages_original_photo_no_get_mutation(self):
        for name,args in [('manage',[]),('add',[]),('edit',[self.promo.pk]),('delete',[self.promo.pk])]:
            response = self.client.get(reverse('recommendations:'+name,args=args))
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'furniture-recommendations.css')
            self.assertNotContains(response,'themes/auto.css')
        response = self.client.get(self.url)
        self.assertContains(response,'/media/products/original-promotion.jpg')
        self.assertNotContains(response,'/thumbs/')
        self.promo.refresh_from_db()
        self.assertTrue(self.promo.is_active)
        self.assertEqual(PromotedProduct.objects.count(),1)

    def test_roles_manager_admin_and_superuser_have_access(self):
        admin = get_user_model().objects.create_user('admin-role',password='test-only')
        admin.profile.role = ROLE_ADMIN
        admin.profile.save()
        superuser = get_user_model().objects.create_superuser('root-user',password='test-only')
        for user in [self.manager,admin,superuser]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code,200)

    def test_customer_staff_and_guest_cannot_change_or_read_promotions(self):
        staff = get_user_model().objects.create_user('staff-customer',password='test-only',is_staff=True)
        customer = get_user_model().objects.create_user('customer',password='test-only')
        for user in [staff,customer,None]:
            if user:self.client.force_login(user)
            else:self.client.logout()
            for name,args in [('manage',[]),('add',[]),('edit',[self.promo.pk]),('delete',[self.promo.pk]),('toggle_active',[self.promo.pk])]:
                url=reverse('recommendations:'+name,args=args)
                self.assertEqual(self.client.get(url).status_code,302)
                self.assertEqual(self.client.post(url,self.payload()).status_code,302)
            self.assertEqual(PromotedProduct.objects.count(),1)
            self.promo.refresh_from_db()
            self.assertTrue(self.promo.is_active)

    def test_create_edit_keep_existing_id_and_other_records(self):
        response=self.client.post(reverse('recommendations:add'),self.payload(page='comparison'))
        self.assertRedirects(response,self.url)
        created=PromotedProduct.objects.exclude(pk=self.promo.pk).get()
        response=self.client.post(reverse('recommendations:edit',args=[created.pk]),self.payload(page='recently_viewed',priority=30))
        self.assertRedirects(response,self.url)
        created.refresh_from_db()
        self.assertEqual((created.page,created.priority),('recently_viewed',30))
        self.promo.refresh_from_db()
        self.assertEqual((self.promo.page,self.promo.priority),('wishlist',10))

    def test_toggle_is_post_only_and_delete_get_only_confirms(self):
        toggle=reverse('recommendations:toggle_active',args=[self.promo.pk])
        self.assertEqual(self.client.get(toggle).status_code,405)
        self.client.post(toggle)
        self.promo.refresh_from_db()
        self.assertFalse(self.promo.is_active)
        self.client.post(toggle)
        self.promo.refresh_from_db()
        self.assertTrue(self.promo.is_active)
        delete=reverse('recommendations:delete',args=[self.promo.pk])
        self.assertContains(self.client.get(delete),'Подтвердить удаление')
        self.assertTrue(PromotedProduct.objects.filter(pk=self.promo.pk).exists())
        self.client.post(delete)
        self.assertFalse(PromotedProduct.objects.filter(pk=self.promo.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_csrf_for_every_mutation(self):
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.manager)
        strict.get(reverse('recommendations:add'))
        for name,args in [('add',[]),('edit',[self.promo.pk]),('delete',[self.promo.pk]),('toggle_active',[self.promo.pk])]:
            self.assertEqual(strict.post(reverse('recommendations:'+name,args=args),self.payload()).status_code,403)
        self.assertEqual(PromotedProduct.objects.count(),1)

    def test_invalid_form_preserves_data(self):
        response=self.client.post(reverse('recommendations:edit',args=[self.promo.pk]),self.payload(page='not-a-page',priority=-1,product=999999))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors)
        self.promo.refresh_from_db()
        self.assertEqual((self.promo.page,self.promo.priority),('wishlist',10))

    def test_datetime_local_round_trip_keeps_timezone_seconds_and_microseconds(self):
        self.promo.start_date=timezone.now().replace(microsecond=123456)
        self.promo.end_date=self.promo.start_date+timedelta(days=3)
        self.promo.save()
        expected_start=self.promo.start_date
        expected_end=self.promo.end_date
        form=PromotedProductForm(instance=self.promo)
        dates={name:re.search(r'value="([^"]+)"',str(form[name])).group(1) for name in ['start_date','end_date']}
        self.assertIn('T',dates['start_date'])
        bound=PromotedProductForm(self.payload(**dates),instance=self.promo)
        self.assertTrue(bound.is_valid(),bound.errors)
        self.assertEqual(bound.cleaned_data['start_date'],expected_start)
        self.assertEqual(bound.cleaned_data['end_date'],expected_end)
        bound.save()
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.start_date,expected_start)
        self.assertEqual(self.promo.end_date,expected_end)

    def test_schedule_priority_page_and_publication_rules_retained(self):
        now=timezone.now()
        other=Product.objects.create(title='Полка',slug='shelf-promotion',price=50)
        high=PromotedProduct.objects.create(product=other,page='wishlist',priority=20,start_date=now-timedelta(days=1),end_date=now+timedelta(days=1))
        self.assertEqual(RecommendationService.get_similar_products([],page='wishlist'),[other,self.product])
        for fields in [{'is_active':False},{'start_date':now+timedelta(days=1)},{'end_date':now-timedelta(days=2)},{'page':'comparison'}]:
            high.is_active=True;high.start_date=None;high.end_date=None;high.page='wishlist'
            for key,value in fields.items():setattr(high,key,value)
            high.save()
            self.assertEqual(RecommendationService.get_similar_products([],page='wishlist'),[self.product])
        self.product.is_active=False;self.product.save(update_fields=['is_active'])
        self.assertEqual(RecommendationService.get_similar_products([],page='wishlist'),[])
        self.assertEqual(PromotedProduct.objects.count(),2)

    def test_pagination_and_draft_notice(self):
        self.product.is_active=False;self.product.save(update_fields=['is_active'])
        for i in range(10):PromotedProduct.objects.create(product=self.product,page='comparison',priority=i)
        response=self.client.get(self.url)
        self.assertEqual(len(response.context['promotions']),10)
        self.assertContains(response,'Изделие не опубликовано')
        self.assertContains(response,'?page=2')
        self.assertEqual(len(self.client.get(self.url,{'page':2}).context['promotions']),1)
        self.assertContains(self.client.get(reverse('recommendations:add')),'На текущей мебельной главной')
