from urllib.parse import urlencode
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from apps.users.decorators import role_required
from apps.users.constants import ROLE_MANAGER, ROLE_ADMIN
from .models import CallbackRequest, WorkshopOrder, OrderEvent
from .order_forms import OrderForm


@never_cache
@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_POST
def order_from_inquiry(request, pk):
    with transaction.atomic():
        inquiry = get_object_or_404(CallbackRequest.objects.select_for_update().select_related('product'), pk=pk)
        existing = WorkshopOrder.objects.filter(inquiry=inquiry).first()
        if existing:
            return redirect('appointments:order_detail', pk=existing.pk)
        if inquiry.status == CallbackRequest.STATUS_CANCELLED:
            messages.error(request, 'Обращение отменено. Сначала восстановите его статус для создания заказа.')
            return redirect('appointments:callback_request_list')
        order = WorkshopOrder.objects.create(
            inquiry=inquiry, title=inquiry.product.title if inquiry.product else f'Мебель для {inquiry.name or inquiry.phone}',
            client_name=inquiry.name, phone=inquiry.phone, email=inquiry.email, city=inquiry.city,
            specification=inquiry.comment, note=inquiry.manager_note, responsible=request.user,
        )
        OrderEvent.objects.create(order=order, author=request.user, description=f'Создан из обращения №{inquiry.pk}.')
        inquiry.status = CallbackRequest.STATUS_PROCESSED
        inquiry.save(update_fields=['status','updated_at'])
    return redirect('appointments:order_detail', pk=order.pk)


@never_cache
@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_http_methods(['GET','HEAD'])
def order_list(request):
    rows = WorkshopOrder.objects.select_related('responsible','inquiry')
    q = request.GET.get('q','').strip()[:200]
    stage = request.GET.get('stage','')
    if stage not in dict(WorkshopOrder.STAGES): stage = ''
    mine = request.GET.get('mine') == '1'
    overdue = request.GET.get('overdue') == '1'
    if q:
        match = Q(title__icontains=q) | Q(client_name__icontains=q) | Q(phone__icontains=q)
        number = q.lstrip('#')
        if number.isascii() and number.isdigit() and len(number) <= 18:
            match |= Q(pk=int(number))
        rows = rows.filter(match)
    if stage: rows = rows.filter(stage=stage)
    if mine: rows = rows.filter(responsible=request.user)
    if overdue: rows = rows.filter(due_on__lt=timezone.localdate()).exclude(stage__in=['completed','cancelled'])
    page = Paginator(rows,25).get_page(request.GET.get('page'))
    params = {}
    if q: params['q'] = q
    if stage: params['stage'] = stage
    if mine: params['mine'] = '1'
    if overdue: params['overdue'] = '1'
    return render(request,'appointments/orders/list.html',{'page_obj':page,'query':q,'stage':stage,'mine':mine,'overdue':overdue,'stages':WorkshopOrder.STAGES,'page_query':urlencode(params)})


@never_cache
@role_required(ROLE_MANAGER, ROLE_ADMIN)
@require_http_methods(['GET','HEAD','POST'])
def order_detail(request, pk):
    order = get_object_or_404(WorkshopOrder.objects.select_related('inquiry','responsible'), pk=pk)
    form = OrderForm(request.POST if request.method == 'POST' else None, instance=order)
    conflict = False
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            locked = WorkshopOrder.objects.select_for_update().get(pk=pk)
            if locked.revision != form.cleaned_data['revision']:
                conflict = True
                form.add_error(None, 'Заказ уже изменён другим сотрудником. Ваши данные не записаны. Откройте свежую карточку в новой вкладке и сверьте изменения.')
            else:
                changes = []
                for name in form._meta.fields:
                    previous = getattr(locked,name)
                    current = form.cleaned_data[name]
                    if previous != current:
                        def display(value):
                            if name == 'stage': return dict(WorkshopOrder.STAGES).get(value,value)
                            return 'Не указано' if value is None or value == '' else str(value)
                        changes.append(f'{form.fields[name].label}: {display(previous)} → {display(current)}')
                        setattr(locked,name,current)
                if changes:
                    locked.revision += 1
                    locked.save()
                    OrderEvent.objects.create(order=locked,author=request.user,description='\n'.join(changes))
        if not conflict:
            messages.success(request,'Заказ сохранён.' if changes else 'Изменений нет.')
            return redirect('appointments:order_detail',pk=pk)
    if request.method == 'POST' and 'revision' in form.errors:
        form.add_error(None, 'Не удалось проверить версию заказа. Откройте свежую карточку и повторите изменение.')
    # Bound ModelForm mutates its instance during validation: show the saved summary.
    order.refresh_from_db()
    return render(request,'appointments/orders/detail.html',{'order':order,'form':form,'events':Paginator(order.events.select_related('author'),25).get_page(request.GET.get('history_page')), 'conflict':conflict},status=409 if conflict else 400 if request.method=='POST' else 200)
