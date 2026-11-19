from django.contrib import admin

from .forms import ContactSettingsForm
from .models import ClientShowcase, ContactSettings, TeamMember


@admin.register(ClientShowcase)
class ClientShowcaseAdmin(admin.ModelAdmin):
    list_display = ("name", "project_title", "has_video_review", "sort_order", "is_published", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("name", "vehicle", "rutube_url")

    @admin.display(description="Изделие или проект", ordering="vehicle")
    def project_title(self, obj):
        return obj.vehicle

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "vehicle" and field is not None:
            field.label = "Изделие или проект"
            field.widget.attrs["placeholder"] = "Например, кухня или шкаф для прихожей"
        return field

    @admin.display(boolean=True, description="Видеоотзыв")
    def has_video_review(self, obj):
        return bool(obj.rutube_url)
    list_editable = ("sort_order", "is_published")


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "sort_order", "is_published", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("name", "position")
    list_editable = ("sort_order", "is_published")


@admin.register(ContactSettings)
class ContactSettingsAdmin(admin.ModelAdmin):
    form = ContactSettingsForm
    list_display = ("phone_primary", "address", "is_published", "updated_at")

    def has_add_permission(self, request):
        return not ContactSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


from django.urls import reverse
from django.utils.html import format_html
from .models import EditablePage
from .copy_registry import PAGES


@admin.register(EditablePage)
class EditablePageAdmin(admin.ModelAdmin):
    list_display=('key','updated_at','published_at','editor_link')

    @admin.display(description='Редактор текстов')
    def editor_link(self,obj):
        return format_html('<a href="{}">{}</a>',reverse('home:copy_edit',args=[obj.key]),PAGES.get(obj.key,{}).get('title',obj.key))

    def has_view_permission(self,request,obj=None):
        return (request.user.is_superuser or getattr(getattr(request.user,'profile',None),'role',None) in ('manager','admin')) and super().has_view_permission(request,obj)

    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    def get_readonly_fields(self,request,obj=None):return [field.name for field in self.model._meta.fields]
