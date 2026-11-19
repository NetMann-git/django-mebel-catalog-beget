from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect,render
from django.urls import resolve,reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_safe
from apps.users.decorators import role_required
from apps.users.constants import ROLE_MANAGER,ROLE_ADMIN
from .models import EditablePage
from .copy_registry import PAGES
from .copy_forms import CopyForm


def definition(key):
    if key not in PAGES:raise Http404
    return PAGES[key]


@never_cache
@role_required(ROLE_MANAGER,ROLE_ADMIN)
@require_safe
def copy_list(request):
    stored={row.key:row for row in EditablePage.objects.all()}
    pages=[{'key':key,'title':value['title'],'row':stored.get(key)} for key,value in PAGES.items()]
    return render(request,'home/manage/copy_list.html',{'pages':pages})


@never_cache
@role_required(ROLE_MANAGER,ROLE_ADMIN)
@require_http_methods(['GET','HEAD','POST'])
def copy_edit(request,key):
    info=definition(key)
    row=EditablePage.objects.filter(key=key).first()
    data=row.draft if row and isinstance(row.draft,dict) else {}
    initial={name:data.get(name,field['default']) for name,field in info['fields'].items()}
    initial['revision']=row.revision if row else 0
    form=CopyForm(key,request.POST if request.method=='POST' else None,initial=initial)
    conflict=False
    if request.method=='POST' and form.is_valid():
        action=request.POST.get('action','save')
        if action not in ('save','publish'):
            form.add_error(None,'Неизвестное действие. Выберите сохранение черновика или публикацию.')
        else:
            with transaction.atomic():
                locked,_=EditablePage.objects.select_for_update().get_or_create(key=key)
                if locked.revision != form.cleaned_data['revision']:
                    conflict=True
                    form.add_error(None,'Другой сотрудник уже изменил эти тексты. Ваши данные не записаны. Откройте свежий редактор и сверьте изменения.')
                else:
                    values={name:form.cleaned_data[name] for name in info['fields']}
                    locked.draft=values
                    if action=='publish':
                        locked.published=values.copy();locked.published_at=timezone.now()
                    locked.revision+=1;locked.updated_by=request.user;locked.save()
            if not conflict:
                messages.success(request,'Тексты опубликованы.' if action=='publish' else 'Черновик сохранён. Посетители по-прежнему видят опубликованные тексты.')
                return redirect('home:copy_edit',key=key)
    row=EditablePage.objects.filter(key=key).first()
    return render(request,'home/manage/copy_edit.html',{'copy_key':key,'copy_title':info['title'],'form':form,'row':row,'conflict':conflict,'public_url':reverse(info['route'])+('#callback' if key=='callback' else '')},status=409 if conflict else 400 if request.method=='POST' else 200)


@never_cache
@role_required(ROLE_MANAGER,ROLE_ADMIN)
@require_safe
def copy_preview(request,key):
    info=definition(key)
    request.copy_preview_key=key
    request.copy_preview_label=info['title']
    response=resolve(reverse(info['route'])).func(request)
    response['X-Robots-Tag']='noindex, nofollow'
    return response
