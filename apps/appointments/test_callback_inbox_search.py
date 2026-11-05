"""Шаг 71: поиск приватных обращений, страницы и безопасный возврат к выборке."""
from urllib.parse import urlsplit, parse_qs
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.products.models import Product
from .models import CallbackRequest

class CallbackInboxSearchTests(TestCase):
    def setUp(self):
        user=get_user_model().objects.create_user('inbox-manager')
        user.profile.role='manager';user.profile.save(update_fields=['role']);self.client.force_login(user)
        self.url=reverse('appointments:callback_request_list')
        self.product=Product.objects.create(title='Гардеробная Лофт',slug='inbox-loft',price=100)
        self.item=CallbackRequest.objects.create(name='Анна',phone='+7 (999) 123-45-67',email='Anna@Example.test',
            city='Краснодар',comment='Нужен шкаф 180 см. a+b[0]',product=self.product,source='product_order')
        self.other=CallbackRequest.objects.create(name='Пётр',phone='+78880000000',status='processed')

    def ids(self,response):return set(response.context['callbacks'].values_list('pk',flat=True))

    def test_searches_fields_unicode_and_formatted_phone(self):
        for q in ['анна','EXAMPLE.TEST','краснодар','лофт','ШКАФ 180','9991234567','+7 999 123 45 67','a+b[0]']:
            with self.subTest(q=q):
                self.assertEqual(self.ids(self.client.get(self.url,{'q':q})),{self.item.pk})
        self.assertFalse(self.ids(self.client.get(self.url,{'q':'.*'})))

    def test_status_search_counts_and_empty_state(self):
        r=self.client.get(self.url,{'q':'пётр','status':'new'})
        self.assertEqual(r.context['matched_total'],0);self.assertEqual(r.context['total'],2);self.assertEqual(r.context['new_count'],1)
        self.assertContains(r,'Обращения не найдены')
        r=self.client.get(self.url,{'q':'пётр','status':'invalid'})
        self.assertEqual(r.context['status'],'');self.assertEqual(self.ids(r),{self.other.pk})

    def test_pages_are_bounded_stable_and_preserve_filter_links(self):
        batch=[CallbackRequest.objects.create(name='Клиент',phone='+79990000000',comment='Партия заказов') for _ in range(25)]
        first=self.client.get(self.url,{'q':'партия','status':'new'})
        second=self.client.get(self.url,{'q':'партия','status':'new','page':2})
        self.assertEqual(len(first.context['callbacks']),20);self.assertEqual(len(second.context['callbacks']),5)
        self.assertEqual(first.context['matched_total'],25)
        self.assertFalse(self.ids(first)&self.ids(second))
        self.assertEqual(self.ids(first)|self.ids(second),{x.pk for x in batch})
        self.assertEqual(first.context['callbacks'][0].pk,batch[-1].pk)
        self.assertContains(first,'page=2');self.assertContains(second,'Страница 2 из 2')
        self.assertContains(first,'name="current_query" value="партия"')
        for page in ['nonsense','99999']:
            self.assertEqual(self.client.get(self.url,{'q':'партия','page':page}).status_code,200)

    def test_status_update_preserves_only_internal_filter_parameters(self):
        q='Анна & <script>alert(1)</script>'
        target=reverse('appointments:callback_request_status_update',args=[self.item.pk])
        r=self.client.post(target,{'status':'processed','current_filter':'new','current_query':q,'current_page':'2','next':'https://evil.invalid/'})
        self.assertEqual(r.status_code,302)
        location=urlsplit(r['Location']);self.assertEqual(location.netloc,'');self.assertEqual(location.path,self.url)
        self.assertEqual(parse_qs(location.query),{'status':['new'],'q':[q],'page':['2']})
        self.item.refresh_from_db();self.assertEqual(self.item.status,'processed')
        self.assertEqual(self.item.comment,'Нужен шкаф 180 см. a+b[0]')

    def test_query_is_bounded_escaped_and_search_does_not_write_data(self):
        before=list(CallbackRequest.objects.order_by('pk').values())
        r=self.client.get(self.url,{'q':'<script>alert(99)</script>'})
        self.assertNotContains(r,'value="<script>');self.assertContains(r,'&lt;script&gt;')
        r=self.client.get(self.url,{'q':'x'*500})
        self.assertEqual(len(r.context['query']),200)
        self.assertEqual(list(CallbackRequest.objects.order_by('pk').values()),before)

    def test_guest_and_customer_cannot_search_private_requests(self):
        outsider=Client();self.assertEqual(outsider.get(self.url,{'q':'Анна'}).status_code,302)
        customer=get_user_model().objects.create_user('inbox-client');outsider.force_login(customer)
        r=outsider.get(self.url,{'q':'Анна'})
        self.assertEqual(r.status_code,302);self.assertNotIn(self.item.phone,r.content.decode())
