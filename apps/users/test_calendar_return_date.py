"""шаг 40: calendar POST returns to its validated selected date."""
from datetime import date,time
from django.contrib.auth import get_user_model
from django.test import Client,TestCase
from django.urls import reverse
from apps.appointments.models import Appointment,WorkingHours


class CalendarReturnDateTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('return-consultant')
        self.user.profile.role='consultant';self.user.profile.save(update_fields=['role'])
        self.client.force_login(self.user)
        self.day=date(2026,11,10)
        WorkingHours.objects.create(day_of_week=self.day.weekday(),start_time=time(10),end_time=time(11),is_active=True)
        self.calendar=reverse('users:consultant_calendar');self.url=reverse('users:consultant_create_appointment')
        self.target=self.calendar+'?date='+self.day.isoformat()
        self.payload={'date':self.day.isoformat(),'time':'10:30','name':'Клиент','phone':'000'}

    def test_success_with_csrf_returns_selected_day_and_shows_booked_slot(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        client.get(self.target);token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.url,self.payload).status_code,403)
        response=client.post(self.url,{**self.payload,'csrfmiddlewaretoken':token},follow=True)
        self.assertEqual(response.redirect_chain,[(self.target,302)])
        self.assertEqual(response.context['date'],self.day)
        self.assertEqual([s['is_booked'] for s in response.context['slots']],[False,True])
        self.assertContains(response,'создана.')
        self.assertEqual(Appointment.objects.count(),1)

    def test_busy_slot_returns_same_day_without_duplicate(self):
        Appointment.objects.create(date=self.day,time=time(10,30),name='Первый',phone='000',status='confirmed')
        response=self.client.post(self.url,self.payload,follow=True)
        self.assertEqual(response.redirect_chain,[(self.target,302)])
        self.assertContains(response,'уже занят')
        self.assertEqual(Appointment.objects.count(),1)

    def test_required_field_or_invalid_time_keeps_valid_day_without_writes(self):
        for changes in [{'name':''},{'phone':''},{'time':''},{'time':'invalid'}]:
            with self.subTest(changes=changes):
                response=self.client.post(self.url,{**self.payload,**changes},follow=True)
                self.assertEqual(response.redirect_chain,[(self.target,302)])
                self.assertFalse(Appointment.objects.exists())

    def test_invalid_or_external_date_falls_back_to_local_calendar(self):
        for value in ['', 'invalid', '2026-02-30', 'https://untrusted.example/', '2026-11-10&next=https://untrusted.example/']:
            with self.subTest(value=value):
                response=self.client.post(self.url,{**self.payload,'date':value})
                self.assertEqual(response['Location'],self.calendar)
                self.assertFalse(Appointment.objects.exists())

    def test_get_and_customer_keep_previous_redirect(self):
        self.assertRedirects(self.client.get(self.url),self.calendar)
        self.user.profile.role='customer';self.user.profile.save(update_fields=['role'])
        self.assertRedirects(self.client.post(self.url,self.payload),reverse('users:dashboard'))
        self.assertFalse(Appointment.objects.exists())
