"""шаг 37: consultant furniture layout retains POST status actions and CSRF."""
from django.test import Client
from django.urls import reverse
from apps.users.test_consultant_product_title import ConsultantProductTitleTests


class FurnitureConsultantTests(ConsultantProductTitleTests):
    def test_layout_links_and_empty_state(self):
        self.user.profile.role = 'consultant'; self.user.profile.save(update_fields=['role'])
        response = self.client.get(self.url)
        for text in ['furniture-consultant.css','noindex, nofollow','Панель консультанта',
                     'fco-table-scroll', 'aria-label="Статус записи', reverse('users:consultant_calendar'),
                     reverse('users:dashboard')]:
            self.assertContains(response,text)
        self.assertNotContains(response,'themes/auto.css')
        self.assertNotContains(response,'Подберем АВТО')
        self.record.delete()
        self.assertContains(self.client.get(self.url),'Записей пока нет')

    def test_existing_post_status_update_and_csrf_still_work(self):
        self.user.profile.role = 'consultant'; self.user.profile.save(update_fields=['role'])
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        client.get(self.url)
        token = client.cookies['csrftoken'].value
        target = reverse('users:appointment_update_status',args=[self.record.pk])
        self.assertEqual(client.post(target,{'status':'completed'}).status_code,403)
        self.record.refresh_from_db(); self.assertEqual(self.record.status,'cancelled')
        response = client.post(target,{'status':'completed','csrfmiddlewaretoken':token},follow=True)
        self.assertEqual(response.redirect_chain,[(self.url,302)])
        self.assertContains(response,'Статус записи изменён')
        self.record.refresh_from_db(); self.assertEqual(self.record.status,'completed')
        client.post(target,{'status':'not-a-status','csrfmiddlewaretoken':token})
        self.record.refresh_from_db(); self.assertEqual(self.record.status,'completed')

    def test_customer_cannot_update_status(self):
        target = reverse('users:appointment_update_status',args=[self.record.pk])
        response = self.client.post(target,{'status':'completed'},follow=True)
        self.assertEqual(response.redirect_chain,[(reverse('users:dashboard'),302)])
        self.record.refresh_from_db(); self.assertEqual(self.record.status,'cancelled')
