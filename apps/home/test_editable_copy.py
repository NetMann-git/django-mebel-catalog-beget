from django.contrib.auth import get_user_model
from django.test import TestCase,Client
from django.urls import reverse
from .models import EditablePage
from .copy_registry import PAGES


class EditableCopyTests(TestCase):
    def setUp(self):
        self.manager=get_user_model().objects.create_user('copy-manager')
        self.manager.profile.role='manager';self.manager.profile.save()
        self.customer=get_user_model().objects.create_user('copy-customer')
        self.client.force_login(self.manager)

    def data(self,key,revision=0,action='save',**changes):
        data={name:field['default'] for name,field in PAGES[key]['fields'].items()}
        data.update(revision=revision,action=action,**changes)
        return data

    def edit(self,key):return reverse('home:copy_edit',args=[key])
    def preview(self,key):return reverse('home:copy_preview',args=[key])

    def test_reading_editors_and_public_defaults_creates_no_rows(self):
        self.assertContains(self.client.get(reverse('home:copy_list')),'Содержимое сайта')
        for key,definition in PAGES.items():
            response=self.client.get(self.edit(key))
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'Предпросмотр сохранённого черновика')
            response=self.client.get(reverse(definition['route']))
            self.assertEqual(response.status_code,200)
            if key!='callback':self.assertContains(response,definition['fields']['heading']['default'].split('\n')[0])
        self.assertFalse(EditablePage.objects.exists())
        self.assertContains(self.client.get(reverse('users:manager_dashboard')),'Тексты страниц, услуги и вопросы-ответы')

    def test_draft_is_private_publish_changes_public_and_later_draft_keeps_published(self):
        key='home';public=Client()
        self.assertEqual(self.client.post(self.edit(key),self.data(key,heading='Новый черновик')).status_code,302)
        self.assertNotContains(public.get('/'),'Новый черновик')
        preview=self.client.get(self.preview(key))
        self.assertContains(preview,'Новый черновик')
        self.assertContains(preview,'Предпросмотр черновика')
        self.assertEqual(preview['X-Robots-Tag'],'noindex, nofollow')
        self.assertIn('no-store',preview['Cache-Control'])
        self.assertEqual(self.client.post(self.edit(key),self.data(key,revision=1,action='publish',heading='Опубликованная главная')).status_code,302)
        self.assertContains(public.get('/'),'Опубликованная главная')
        self.client.post(self.edit(key),self.data(key,revision=2,heading='Следующий черновик'))
        self.assertContains(public.get('/'),'Опубликованная главная')
        self.assertNotContains(public.get('/'),'Следующий черновик')
        self.assertContains(self.client.get(self.preview(key)),'Следующий черновик')
        row=EditablePage.objects.get(key=key)
        self.assertIsNotNone(row.published_at);self.assertEqual(row.updated_by,self.manager)

    def test_stale_form_and_invalid_actions_do_not_overwrite(self):
        key='about'
        self.client.post(self.edit(key),self.data(key,action='publish',heading='Сохранённый текст'))
        response=self.client.post(self.edit(key),self.data(key,action='publish',heading='Чужая устаревшая правка'))
        self.assertEqual(response.status_code,409)
        self.assertContains(response,'Ваши данные не записаны',status_code=409)
        self.assertEqual(EditablePage.objects.get(key=key).published['heading'],'Сохранённый текст')
        for action in ('delete','unknown'):
            response=self.client.post(self.edit(key),self.data(key,revision=1,action=action))
            self.assertEqual(response.status_code,400)
        self.assertEqual(EditablePage.objects.get(key=key).revision,1)
        self.assertEqual(self.client.post(self.edit('materials'),self.data('materials',heading='')).status_code,400)
        self.assertFalse(EditablePage.objects.filter(key='materials').exists())

    def test_customer_anonymous_csrf_and_query_cannot_expose_draft(self):
        self.client.post(self.edit('home'),self.data('home',heading='Секретный черновик'))
        public=Client()
        for client in (public,Client()):
            if client is not public:client.force_login(self.customer)
            for url in (self.edit('home'),self.preview('home'),reverse('home:copy_list')):
                self.assertEqual(client.get(url).status_code,302)
            self.assertEqual(client.post(self.edit('home'),self.data('home',action='publish')).status_code,302)
            self.assertNotContains(client.get('/?content_preview=home'),'Секретный черновик')
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.manager)
        self.assertEqual(secure.post(self.edit('home'),self.data('home')).status_code,403)
        self.assertIsNone(EditablePage.objects.get(key='home').published_at)
        self.assertEqual(self.client.get(self.edit('missing')).status_code,404)
        self.assertEqual(self.client.get(self.preview('missing')).status_code,404)

    def test_faq_visibility_service_description_callback_and_html_escaping(self):
        key='home'
        self.client.post(self.edit(key),self.data(key,action='publish',faq_1_question='Новый вопрос',faq_1_answer='Новый ответ'))
        self.assertContains(Client().get('/'),'Новый вопрос')
        row=EditablePage.objects.get(key=key)
        data=self.data(key,revision=row.revision,action='publish');data.pop('faq_1_enabled')
        self.client.post(self.edit(key),data)
        self.assertNotContains(Client().get('/'),PAGES[key]['fields']['faq_1_question']['default'])
        self.client.post(self.edit('services'),self.data('services',action='publish',service_storage_0='Новое описание услуги'))
        self.assertContains(Client().get(reverse('furniture_services')),'Новое описание услуги')
        self.client.post(self.edit('callback'),self.data('callback',action='publish',heading='Обсудим вашу задачу'))
        for url in ('/',reverse('furniture_services'),reverse('furniture_kitchens')):
            self.assertContains(Client().get(url),'Обсудим вашу задачу')
        self.client.post(self.edit('kitchens'),self.data('kitchens',action='publish',heading='<script>alert(1)</script>'))
        response=Client().get(reverse('furniture_kitchens'))
        self.assertNotContains(response,'<script>alert(1)</script>');self.assertContains(response,'&lt;script&gt;')

    def test_every_supported_page_previews_only_its_saved_draft(self):
        public=Client()
        for key,info in PAGES.items():
            marker='Черновик раздела '+key
            self.client.post(self.edit(key),self.data(key,heading=marker))
            self.assertContains(self.client.get(self.preview(key)),marker)
            self.assertNotContains(public.get(reverse(info['route'])),marker)
