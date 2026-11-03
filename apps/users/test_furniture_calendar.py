"""шаг 38: retain calendar slots, permissions and CSRF form contract."""
from datetime import date,time
from django.contrib.auth import get_user_model
from django.test import Client,TestCase
from django.urls import reverse
from apps.appointments.models import Appointment,WorkingHours


class FurnitureCalendarTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('calendar-consultant')
        self.user.profile.role='consultant';self.user.profile.save(update_fields=['role'])
        self.client.force_login(self.user)
        self.day=date(2026,11,10)
        WorkingHours.objects.create(day_of_week=self.day.weekday(),start_time=time(10),end_time=time(11),is_active=True)
        self.url=reverse('users:consultant_calendar');self.create=reverse('users:consultant_create_appointment')
        self.payload={'date':self.day.isoformat(),'time':'10:30','name':'Клиент','phone':'000','email':'qa@example.test','comment':'Тестовый комментарий'}

    def test_slots_navigation_and_existing_form_fields(self):
        Appointment.objects.create(name='Скрытый клиент',phone='123456789',date=self.day,time=time(10),status='confirmed')
        response=self.client.get(self.url,{'date':self.day.isoformat()})
        self.assertEqual([s['is_booked'] for s in response.context['slots']],[True,False])
        for text in ['furniture-calendar.css','noindex, nofollow','consultant.js','data-date="2026-11-10"',
                     'data-time="10:30"','?date=2026-11-09','?date=2026-11-11',self.create,
                     'id="slot-form-modal"','id="slot-date"','id="slot-time"','Закрыть форму записи']:
            self.assertContains(response,text)
        for name in ['date','time','name','phone','email','comment']:
            self.assertContains(response,'name="'+name+'"')
        for text in ['data-time="10:00"','Скрытый клиент','123456789','themes/auto.css']:
            self.assertNotContains(response,text)

    def test_nonworking_day_and_invalid_date_are_handled(self):
        response=self.client.get(self.url,{'date':'2026-11-11'})
        self.assertContains(response,'В этот день мастерская не работает.')
        self.assertEqual(response.context['slots'],[])
        self.assertEqual(self.client.get(self.url,{'date':'invalid'}).status_code,200)

    def test_create_with_csrf_and_duplicate_slot_keeps_existing_record(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        client.get(self.url,{'date':self.day.isoformat()});token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.create,self.payload).status_code,403)
        self.assertFalse(Appointment.objects.exists())
        response=client.post(self.create,{**self.payload,'csrfmiddlewaretoken':token})
        self.assertEqual(response.status_code,302)
        record=Appointment.objects.get();self.assertEqual(record.status,'pending')
        self.assertEqual(record.comment,self.payload['comment'])
        client.post(self.create,{**self.payload,'csrfmiddlewaretoken':token})
        self.assertEqual(Appointment.objects.count(),1)
        client.post(self.create,{**self.payload,'time':'invalid','csrfmiddlewaretoken':token})
        self.assertEqual(Appointment.objects.count(),1)

    def test_allowed_roles_and_customer_guest_denied(self):
        for role in ['consultant','manager','admin']:
            self.user.profile.role=role;self.user.profile.save(update_fields=['role'])
            self.assertEqual(self.client.get(self.url).status_code,200)
        self.user.profile.role='customer';self.user.profile.save(update_fields=['role'])
        self.assertRedirects(self.client.get(self.url),reverse('users:dashboard'))
        self.assertRedirects(self.client.post(self.create,self.payload),reverse('users:dashboard'))
        self.assertFalse(Appointment.objects.exists())
        self.client.logout()
        self.assertRedirects(self.client.get(self.url),reverse('users:login')+'?next='+self.url)
