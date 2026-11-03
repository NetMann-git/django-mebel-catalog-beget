"""шаг 39: the status form offers only transitions already accepted by backend."""
from datetime import date,time
from html.parser import HTMLParser
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.appointments.models import Appointment


class StatusSelect(HTMLParser):
    def __init__(self, response):
        super().__init__();self.select=None;self.options=[];self.inside=False
        self.feed(response.content.decode())
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='select' and attrs.get('name')=='status':self.select=attrs;self.inside=True
        if tag=='option' and self.inside:self.options.append(attrs)
    def handle_endtag(self,tag):
        if tag=='select':self.inside=False


class ConsultantStatusChoiceTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('status-consultant')
        self.user.profile.role='consultant';self.user.profile.save(update_fields=['role'])
        self.client.force_login(self.user)
        self.record=Appointment.objects.create(name='Клиент',phone='000',date=date(2026,11,10),time=time(10),status='new')
        self.url=reverse('users:consultant_dashboard')
        self.target=reverse('users:appointment_update_status',args=[self.record.pk])

    def test_form_enabled_choices_match_existing_backend_for_every_current_status(self):
        for status,label in Appointment.STATUS_CHOICES:
            with self.subTest(status=status):
                Appointment.objects.filter(pk=self.record.pk).update(status=status)
                response=self.client.get(self.url);form=StatusSelect(response)
                self.assertIn('required',form.select)
                self.assertEqual([o['value'] for o in form.options if 'disabled' not in o],['confirmed','completed','cancelled'])
                selected=[o for o in form.options if 'selected' in o]
                self.assertEqual(len(selected),1)
                if status in ['new','pending']:
                    self.assertEqual(selected[0]['value'],'');self.assertIn('disabled',selected[0])
                    self.assertContains(response,'Выберите статус')
                else:self.assertEqual(selected[0]['value'],status)
                self.assertContains(response,label)

    def test_each_offered_transition_is_accepted_from_new_and_pending(self):
        for start in ['new','pending']:
            for target in ['confirmed','completed','cancelled']:
                with self.subTest(start=start,target=target):
                    Appointment.objects.filter(pk=self.record.pk).update(status=start)
                    response=self.client.post(self.target,{'status':target},follow=True)
                    self.assertEqual(response.redirect_chain,[(self.url,302)])
                    self.assertContains(response,'Статус записи изменён')
                    self.record.refresh_from_db();self.assertEqual(self.record.status,target)

    def test_empty_or_unsupported_status_still_cannot_change_record(self):
        for status in ['', 'pending', 'new', 'invalid']:
            response=self.client.post(self.target,{'status':status},follow=True)
            self.assertContains(response,'Неверный статус.')
            self.record.refresh_from_db();self.assertEqual(self.record.status,'new')
