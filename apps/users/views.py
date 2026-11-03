# apps/users/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment, CallbackRequest
from apps.products.models import Product
from .decorators import role_required
from .constants import ROLE_MANAGER, ROLE_ADMIN
from apps.wishlist.models import Favorite
from apps.reviews.models import Review
from .forms import UserRegistrationForm, ProfileEditForm
from django.db import transaction

# apps/users/views.py

from django.db.models import Count, Avg, Sum, Q
from datetime import datetime, timedelta
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth


@login_required
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def manager_dashboard(request):
    """Workshop overview, retaining existing appointment statistics."""
    catalog_stats = Product.objects.aggregate(
        total=Count('pk'),
        published=Count('pk', filter=Q(is_active=True)),
        drafts=Count('pk', filter=Q(is_active=False)),
    )
    callback_stats = CallbackRequest.objects.aggregate(
        total=Count('pk'),
        new=Count('pk', filter=Q(status=CallbackRequest.STATUS_NEW)),
        processed=Count('pk', filter=Q(status=CallbackRequest.STATUS_PROCESSED)),
        cancelled=Count('pk', filter=Q(status=CallbackRequest.STATUS_CANCELLED)),
    )

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Записи за период
    appointments = Appointment.objects.all()
    appointments_today = appointments.filter(date=today)
    appointments_week = appointments.filter(date__gte=week_ago)
    appointments_month = appointments.filter(date__gte=month_ago)
    
    # Статистика по статусам
    stats = {
        'total': appointments.count(),
        'today': appointments_today.count(),
        'week': appointments_week.count(),
        'month': appointments_month.count(),
        'pending': appointments.filter(status='pending').count(),
        'confirmed': appointments.filter(status='confirmed').count(),
        'completed': appointments.filter(status='completed').count(),
        'cancelled': appointments.filter(status='cancelled').count(),
        'by_status': appointments.values('status').annotate(count=Count('id')),
        'by_day': appointments_month.annotate(day=TruncDay('date')).values('day').annotate(count=Count('id')).order_by('day'),
        'by_week': appointments_month.annotate(week=TruncWeek('date')).values('week').annotate(count=Count('id')).order_by('week'),
    }
    
    # Популярные товары (по записям)
    popular_products = (
        Appointment.objects
        .filter(product__isnull=False)
        .values('product__title', 'product__id')  # ИСПРАВЛЕНО: name → title
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    # Отзывы
    reviews = Review.objects.all()
    review_stats = {
        'total': reviews.count(),
        'avg_rating': reviews.aggregate(Avg('rating'))['rating__avg'] or 0,
        'by_rating': reviews.values('rating').annotate(count=Count('id')).order_by('-rating'),
        'with_photo': reviews.filter(images__isnull=False).distinct().count(),
        'verified': reviews.filter(is_verified=True).count(),
        'unverified': reviews.filter(is_verified=False).count(),
    }
    
    # Активность продавцов (кто создал больше всего записей)
    consultant_activity = (
        Appointment.objects
        .values('user__username', 'user__first_name', 'user__last_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    context = {
        'catalog_stats': catalog_stats,
        'callback_stats': callback_stats,
        'stats': stats,
        'popular_products': popular_products,
        'review_stats': review_stats,
        'consultant_activity': consultant_activity,
        'today': today,
    }
    return render(request, 'users/manager_dashboard.html', context)


def register(request):
    """Регистрация нового пользователя."""
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('users:dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'users/register.html', {'form': form})


@login_required
def dashboard(request):
    """Главная страница личного кабинета."""
    user = request.user
    context = {
        'user': user,
        'profile': user.profile,
        'appointments_count': Appointment.objects.filter(user=user).count(),
        'favorites_count': Favorite.objects.filter(user=user).count(),
        'reviews_count': Review.objects.filter(user=user).count(),
    }
    return render(request, 'users/dashboard.html', context)


@login_required
def profile_edit(request):
    """Редактирование профиля."""
    user = request.user
    profile = user.profile
    initial = {name: getattr(user, name) for name in ('first_name', 'last_name', 'email')}
    initial['phone'] = profile.phone
    
    if request.method == 'POST':
        # Keep the previous partial-POST behavior: missing fields stay unchanged.
        form = ProfileEditForm({name: request.POST.get(name, value) for name, value in initial.items()})
        if form.is_valid():
            with transaction.atomic():
                for name in ('first_name', 'last_name', 'email'):
                    setattr(user, name, form.cleaned_data[name])
                user.save(update_fields=['first_name', 'last_name', 'email'])
                profile.phone = form.cleaned_data['phone']
                profile.save(update_fields=['phone'])
            messages.success(request, 'Профиль успешно обновлён!')
            return redirect('users:dashboard')
    else:
        form = ProfileEditForm(initial=initial)
    
    return render(request, 'users/profile_edit.html', {
        'user': user,
        'profile': profile,
        'form': form,
    })


@login_required
def appointments_history(request):
    """История записей на примерку."""
    appointments = Appointment.objects.filter(user=request.user).order_by('-date', '-time')
    return render(request, 'users/appointments_history.html', {'appointments': appointments})


@login_required
def favorites_list(request):
    """Список избранных товаров."""
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    return render(request, 'users/favorites_list.html', {'favorites': favorites})


@login_required
def reviews_list(request):
    """Список отзывов пользователя."""
    reviews = Review.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'users/reviews_list.html', {'reviews': reviews})


# ===== ПРОДАВЕЦ =====

@login_required
def consultant_dashboard(request):
    """Дашборд продавца."""
    if request.user.profile.role not in ['consultant', 'manager', 'admin']:
        messages.error(request, 'У вас нет доступа к этой странице.')
        return redirect('users:dashboard')
    
    appointments = Appointment.objects.all().order_by('-date', '-time')
    
    # Статистика
    today = timezone.now().date()
    stats = {
        'total': appointments.count(),
        'pending': appointments.filter(status='pending').count(),
        'today': appointments.filter(date=today).count(),
        'confirmed': appointments.filter(status='confirmed').count(),
        'completed': appointments.filter(status='completed').count(),
        'cancelled': appointments.filter(status='cancelled').count(),
    }
    
    context = {
        'appointments': appointments,
        'stats': stats,
        'today': today,
    }
    return render(request, 'users/consultant_dashboard.html', context)


@login_required
def consultant_calendar(request):
    """Календарь записей для продавца (шахматка)."""
    if request.user.profile.role not in ['consultant', 'manager', 'admin']:
        messages.error(request, 'У вас нет доступа к этой странице.')
        return redirect('users:dashboard')
    
    from datetime import datetime, timedelta
    from apps.appointments.models import WorkingHours
    
    date_str = request.GET.get('date')
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date = timezone.now().date()
    else:
        date = timezone.now().date()
    
    day_of_week = date.weekday()
    
    # Получаем рабочие часы
    try:
        working_hours = WorkingHours.objects.get(day_of_week=day_of_week, is_active=True)
    except WorkingHours.DoesNotExist:
        working_hours = None
    
    # Генерируем слоты
    slots = []
    if working_hours:
        start = datetime.combine(date, working_hours.start_time)
        end = datetime.combine(date, working_hours.end_time)
        current = start
        while current < end:
            time_str = current.strftime('%H:%M')
            is_booked = Appointment.objects.filter(
                date=date,
                time=current.time(),
                status__in=['pending', 'confirmed']
            ).exists()
            slots.append({
                'time': time_str,
                'datetime': current,
                'is_booked': is_booked,
            })
            current += timedelta(minutes=30)
    
    context = {
        'date': date,
        'slots': slots,
        'working_hours': working_hours,
        'prev_date': date - timedelta(days=1),
        'next_date': date + timedelta(days=1),
    }
    return render(request, 'users/consultant_calendar.html', context)


@login_required
def consultant_create_appointment(request):
    """Создание записи на примерку продавцом (без доступа к админке)."""
    if request.user.profile.role not in ['consultant', 'manager', 'admin']:
        messages.error(request, 'У вас нет доступа к этой странице.')
        return redirect('users:dashboard')
    
    if request.method == 'POST':
        from datetime import datetime
        
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')
        comment = request.POST.get('comment', '')
        
        if not date_str or not time_str or not name or not phone:
            messages.error(request, 'Заполните все обязательные поля.')
            return redirect('users:consultant_calendar')
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            messages.error(request, 'Неверный формат даты или времени.')
            return redirect('users:consultant_calendar')
        
        # Проверяем, не занят ли слот
        if Appointment.objects.filter(date=date, time=time, status__in=['pending', 'confirmed']).exists():
            messages.error(request, f'Слот {time_str} на {date_str} уже занят.')
            return redirect('users:consultant_calendar')
        
        # Создаём запись
        appointment = Appointment.objects.create(
            date=date,
            time=time,
            name=name,
            phone=phone,
            email=email,
            comment=comment,
            status='pending',
        )
        messages.success(request, f'Запись для {name} на {date} {time} создана.')
        return redirect('users:consultant_calendar')
    
    return redirect('users:consultant_calendar')


@login_required
def appointment_update_status(request, appointment_id):
    """Обновление статуса записи."""
    if request.user.profile.role not in ['consultant', 'manager', 'admin']:
        messages.error(request, 'У вас нет доступа к этой странице.')
        return redirect('users:dashboard')
    
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ['confirmed', 'completed', 'cancelled']:
            appointment.status = status
            appointment.save()
            messages.success(request, f'Статус записи изменён на "{appointment.get_status_display()}"')
        else:
            messages.error(request, 'Неверный статус.')
    
    return redirect('users:consultant_dashboard')
