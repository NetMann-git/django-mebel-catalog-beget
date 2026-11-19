"""Private workshop orders linked to the original customer request."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from django.utils import timezone


class WorkshopOrder(models.Model):
    STAGES = [('calculation','Расчёт'),('measurement','Замер'),('approval','Согласование'),('production','Изготовление'),('installation','Монтаж'),('completed','Завершён'),('cancelled','Отменён')]
    inquiry = models.OneToOneField('appointments.CallbackRequest', on_delete=models.PROTECT, related_name='workshop_order', verbose_name='Исходное обращение')
    title = models.CharField(max_length=255, verbose_name='Название заказа')
    client_name = models.CharField(max_length=100, blank=True, verbose_name='Клиент')
    phone = models.CharField(max_length=30, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    city = models.CharField(max_length=120, blank=True, verbose_name='Город / населённый пункт')
    specification = models.TextField(blank=True, verbose_name='Задача и комплектация')
    stage = models.CharField(max_length=20, choices=STAGES, default='calculation', db_index=True, verbose_name='Этап заказа')
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='workshop_orders', verbose_name='Ответственный')
    due_on = models.DateField(null=True, blank=True, db_index=True, verbose_name='Плановый срок завершения')
    agreed_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Согласованная стоимость, ₽')
    paid = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Оплачено, ₽')
    note = models.TextField(blank=True, max_length=4000, verbose_name='Внутренняя заметка')
    revision = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at','-pk']
        verbose_name = 'Заказ мастерской'
        verbose_name_plural = 'Заказы мастерской'
        constraints = [
            models.CheckConstraint(condition=Q(paid__gte=0), name='workshop_paid_nonnegative'),
            models.CheckConstraint(condition=Q(agreed_total__isnull=True) | Q(agreed_total__gte=0), name='workshop_total_nonnegative'),
            models.CheckConstraint(condition=(Q(agreed_total__isnull=True, paid=0) | Q(agreed_total__isnull=False, paid__lte=F('agreed_total'))), name='workshop_paid_within_total'),
        ]

    def clean(self):
        errors = {}
        if self.agreed_total is not None and self.agreed_total < 0:
            errors['agreed_total'] = 'Стоимость не может быть отрицательной.'
        if self.paid is not None:
            if self.paid < 0:
                errors['paid'] = 'Оплата не может быть отрицательной.'
            elif (self.agreed_total is None and self.paid > 0) or (self.agreed_total is not None and self.paid > self.agreed_total):
                errors['paid'] = 'Сначала укажите согласованную стоимость. Оплата не должна превышать её.'
        if errors:
            raise ValidationError(errors)

    @property
    def balance(self):
        return None if self.agreed_total is None else self.agreed_total - self.paid

    @property
    def overdue(self):
        return bool(self.due_on and self.due_on < timezone.localdate() and self.stage not in ('completed','cancelled'))

    def __str__(self):
        return f'Заказ №{self.pk} — {self.title}'


class OrderEvent(models.Model):
    order = models.ForeignKey(WorkshopOrder, on_delete=models.CASCADE, related_name='events')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at','-pk']
