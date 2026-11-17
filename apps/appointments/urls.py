# apps/appointments/urls.py

from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    path('car-inquiry/<int:product_id>/', views.car_inquiry, name='car_inquiry'),
    path('form/', views.appointment_form, name='form'),
    path('form/<int:product_id>/', views.appointment_form, name='form_for_product'),
    path('submit/', views.appointment_submit, name='submit'),
    path('callback-submit/', views.callback_submit, name='callback_submit'),
    path('callbacks/', views.callback_request_list, name='callback_request_list'),
    path('callbacks/<int:pk>/photo/', views.callback_reference_photo, name='callback_reference_photo'),
    path('callbacks/<int:pk>/status/', views.callback_request_status_update, name='callback_request_status_update'),
    path('slots/<str:date>/', views.get_available_slots, name='slots'),
]
