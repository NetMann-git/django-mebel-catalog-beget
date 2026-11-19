from django.urls import path

from . import manage_views, copy_views

app_name = "home"

urlpatterns = [
    path('pages/', copy_views.copy_list, name='copy_list'),
    path('pages/<slug:key>/', copy_views.copy_edit, name='copy_edit'),
    path('pages/<slug:key>/preview/', copy_views.copy_preview, name='copy_preview'),
    path("contacts/", manage_views.contacts_manage, name="contacts_manage"),
    path("team/", manage_views.team_list_manage, name="team_list_manage"),
    path("team/create/", manage_views.team_create, name="team_create"),
    path("team/reorder/", manage_views.team_reorder, name="team_reorder"),
    path("team/<int:member_id>/move/", manage_views.team_move, name="team_move"),
    path("team/<int:member_id>/edit/", manage_views.team_edit, name="team_edit"),
    path("team/<int:member_id>/toggle-published/", manage_views.team_toggle_published, name="team_toggle_published"),
    path("team/<int:member_id>/delete/", manage_views.team_delete, name="team_delete"),
    path("clients/", manage_views.client_list_manage, name="client_list_manage"),
    path("clients/create/", manage_views.client_create, name="client_create"),
    path("clients/reorder/", manage_views.client_reorder, name="client_reorder"),
    path("clients/<int:client_id>/move/", manage_views.client_move, name="client_move"),
    path("clients/<int:client_id>/edit/", manage_views.client_edit, name="client_edit"),
    path("clients/<int:client_id>/toggle-published/", manage_views.client_toggle_published, name="client_toggle_published"),
    path("clients/<int:client_id>/delete/", manage_views.client_delete, name="client_delete"),
]
