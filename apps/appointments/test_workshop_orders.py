from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError, transaction
from .models import CallbackRequest, CallbackReferencePhoto, WorkshopOrder, OrderEvent


class WorkshopOrderTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user('manager-orders')
        self.manager.profile.role='manager';self.manager.profile.save()
        self.customer = get_user_model().objects.create_user('customer-orders')
        self.client.force_login(self.manager)
        self.inquiry = CallbackRequest.objects.create(name='Анна',phone='+79991234567',email='anna@example.com',city='Сочи',comment='Кухня 320 см',manager_note='Перезвонить')
        CallbackReferencePhoto.objects.create(callback=self.inquiry,content=b'private')
        self.create_url=reverse('appointments:order_from_inquiry',args=[self.inquiry.pk])

    def create(self):
        self.client.post(self.create_url)
        return WorkshopOrder.objects.get()

    def data(self, order, **extra):
        return {'title':order.title,'client_name':order.client_name,'phone':order.phone,'email':order.email,'city':order.city,'specification':order.specification,'stage':order.stage,'responsible':self.manager.pk,'due_on':'','agreed_total':'','paid':'0','note':order.note,'revision':order.revision,**extra}

    def test_conversion_is_post_only_idempotent_and_preserves_source(self):
        self.assertEqual(self.client.get(self.create_url).status_code,405)
        order=self.create()
        self.assertEqual(order.specification,self.inquiry.comment)
        self.assertEqual(order.email,self.inquiry.email)
        self.assertIsNone(order.agreed_total)
        self.assertEqual(order.paid,0)
        self.assertEqual(order.responsible,self.manager)
        self.inquiry.refresh_from_db();self.assertEqual(self.inquiry.status,'processed')
        self.client.post(self.create_url)
        self.assertEqual(WorkshopOrder.objects.count(),1)
        self.assertEqual(OrderEvent.objects.count(),1)
        self.assertEqual(CallbackReferencePhoto.objects.count(),1)
        response=self.client.get(reverse('appointments:callback_request_list'))
        self.assertContains(response,f'Открыть заказ №{order.pk}')
        detail=self.client.get(reverse('appointments:order_detail',args=[order.pk]))
        self.assertContains(detail,'Открыть фото клиента')
        self.assertContains(self.client.get(reverse('users:manager_dashboard')),'Этапы работ, ответственные, сроки и оплата')

    def test_edit_records_history_and_stale_form_cannot_overwrite(self):
        order=self.create();url=reverse('appointments:order_detail',args=[order.pk])
        payload=self.data(order,stage='production',agreed_total='150000',paid='50000',due_on='2027-01-15')
        self.assertEqual(self.client.post(url,payload).status_code,302)
        order.refresh_from_db();self.assertEqual(order.balance,Decimal('100000'))
        self.assertEqual(order.stage,'production');self.assertEqual(order.revision,2)
        self.assertEqual(order.events.count(),2)
        self.assertIn('Изготовление',order.events.first().description)
        payload['stage']='cancelled'
        response=self.client.post(url,payload)
        self.assertEqual(response.status_code,409)
        self.assertContains(response,'Ваши данные не записаны',status_code=409)
        order.refresh_from_db();self.assertEqual(order.stage,'production')
        self.assertEqual(order.events.count(),2)
        self.assertEqual(self.client.post(url,self.data(order,agreed_total='150000',paid='50000',due_on='2027-01-15')).status_code,302)
        self.assertEqual(order.events.count(),2)

    def test_invalid_money_stage_and_responsible_do_not_write(self):
        order=self.create();url=reverse('appointments:order_detail',args=[order.pk])
        for extra in ({'paid':'-1'},{'paid':'1'},{'agreed_total':'-1'},{'agreed_total':'100','paid':'101'},{'stage':'bad'},{'responsible':self.customer.pk},{'revision':''}):
            with self.subTest(extra=extra):self.assertEqual(self.client.post(url,self.data(order,**extra)).status_code,400)
        order.refresh_from_db();self.assertEqual(order.paid,0);self.assertIsNone(order.agreed_total)
        self.assertEqual(order.events.count(),1)
        with self.assertRaises(IntegrityError),transaction.atomic():
            WorkshopOrder.objects.filter(pk=order.pk).update(agreed_total=100,paid=101)

    def test_filters_deadline_and_pagination(self):
        order=self.create();order.due_on=timezone.localdate()-timedelta(days=1);order.save()
        self.assertTrue(order.overdue)
        url=reverse('appointments:order_list')
        for params in ({'q':f'#{order.pk}'},{'mine':'1'},{'overdue':'1'},{'stage':'calculation'}):
            response=self.client.get(url,params);self.assertEqual(list(response.context['page_obj']),[order])
        self.assertEqual(list(self.client.get(url,{'stage':'completed'}).context['page_obj']),[])
        order.stage='completed';order.save()
        self.assertFalse(order.overdue)
        self.assertEqual(list(self.client.get(url,{'overdue':'1'}).context['page_obj']),[])
        for i in range(26):
            inquiry=CallbackRequest.objects.create(phone=f'7999000{i:04}')
            WorkshopOrder.objects.create(inquiry=inquiry,title=f'Заказ {i}',phone=inquiry.phone)
        response=self.client.get(url,{'page':'2'})
        self.assertEqual(len(response.context['page_obj']),2)
        self.assertContains(response,'Не согласована')

    def test_customers_and_anonymous_cannot_read_or_write_and_csrf(self):
        order=self.create();detail=reverse('appointments:order_detail',args=[order.pk]);listing=reverse('appointments:order_list')
        self.client.force_login(self.customer)
        for url in (detail,listing,self.create_url):
            self.assertEqual(self.client.get(url).status_code,302)
            self.assertEqual(self.client.post(url,self.data(order)).status_code,302)
        self.client.logout()
        self.assertEqual(self.client.get(detail).status_code,302)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.manager)
        self.assertEqual(secure.post(detail,self.data(order)).status_code,403)
        self.assertEqual(secure.post(self.create_url).status_code,403)

    def test_cancelled_request_does_not_create_order_and_private_headers(self):
        self.inquiry.status='cancelled';self.inquiry.save()
        self.assertEqual(self.client.post(self.create_url).status_code,302)
        self.assertFalse(WorkshopOrder.objects.exists())
        response=self.client.get(reverse('appointments:order_list'))
        self.assertContains(response,'noindex, nofollow')
        self.assertIn('no-store',response['Cache-Control'])

    def test_history_is_paginated_and_cancelled_inquiry_protected_from_deletion(self):
        from django.db.models.deletion import ProtectedError
        order=self.create()
        OrderEvent.objects.bulk_create([OrderEvent(order=order,author=self.manager,description=f'Изменение {i}') for i in range(26)])
        response=self.client.get(reverse('appointments:order_detail',args=[order.pk]),{'history_page':'2'})
        self.assertEqual(len(response.context['events']),2)
        with self.assertRaises(ProtectedError):self.inquiry.delete()

    def test_malicious_html_remains_text_and_no_order_changes_on_get(self):
        order=self.create();order.title='<script>alert(1)</script>';order.save()
        url=reverse('appointments:order_detail',args=[order.pk])
        response=self.client.get(url)
        self.assertContains(response,'&lt;script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertEqual(order.events.count(),1)
