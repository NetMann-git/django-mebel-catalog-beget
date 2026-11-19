from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.users.constants import ROLE_ADMIN, ROLE_MANAGER
from apps.users.decorators import role_required

from .forms import ClientShowcaseForm, ContactSettingsForm, TeamMemberForm
from .models import ClientShowcase, ContactSettings, TeamMember


def _safe_return(request, fallback):
    target = (request.POST.get("next") or "").strip()
    if (target.startswith("/") and not target.startswith("//") and "\\" not in target
            and url_has_allowed_host_and_scheme(target, allowed_hosts=set())):
        return target
    return reverse(fallback)


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def client_list_manage(request):
    clients = ClientShowcase.objects.all()

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()

    if search:
        clients = clients.filter(Q(name__icontains=search) | Q(vehicle__icontains=search))

    if status == "published":
        clients = clients.filter(is_published=True)
    elif status == "hidden":
        clients = clients.filter(is_published=False)

    total = clients.count()
    sortable = not search and not status

    if sortable:
        client_items = clients
        page_obj = None
    else:
        page_obj = Paginator(clients, 24).get_page(request.GET.get("page"))
        client_items = page_obj.object_list

    return render(
        request,
        "home/manage/clients_list.html",
        {
            "clients": client_items,
            "page_obj": page_obj,
            "total": total,
            "search": search,
            "status": status,
            "sortable": sortable,
        },
    )


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def client_create(request):
    if request.method == "POST":
        form = ClientShowcaseForm(request.POST, request.FILES)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Клиент «{client.name}» создан.')
            return redirect("home:client_list_manage")
    else:
        next_order = (ClientShowcase.objects.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0) + 10
        form = ClientShowcaseForm(initial={"sort_order": next_order, "is_published": True})

    return render(request, "home/manage/client_form.html", {"form": form, "title": "Добавить клиента"})


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def client_edit(request, client_id):
    client = get_object_or_404(ClientShowcase, pk=client_id)

    if request.method == "POST":
        form = ClientShowcaseForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f'Карточка «{client.name}» обновлена.')
            return redirect("home:client_list_manage")
    else:
        form = ClientShowcaseForm(instance=client)

    return render(
        request,
        "home/manage/client_form.html",
        {"form": form, "client": client, "title": "Редактировать клиента"},
    )


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def client_toggle_published(request, client_id):
    client = get_object_or_404(ClientShowcase, pk=client_id)
    client.is_published = not client.is_published
    client.save(update_fields=("is_published", "updated_at"))

    state = "опубликован" if client.is_published else "снят с публикации"
    messages.success(request, f'Клиент «{client.name}» {state}.')
    return redirect(_safe_return(request, "home:client_list_manage"))


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def client_move(request, client_id):
    """Резервное серверное перемещение карточки вверх/вниз без JavaScript."""
    direction = request.POST.get("direction")
    if direction not in {"up", "down"}:
        messages.error(request, "Некорректное направление перемещения.")
        return redirect("home:client_list_manage")

    ordered = list(ClientShowcase.objects.order_by("sort_order", "id"))
    current_index = next((i for i, item in enumerate(ordered) if item.pk == client_id), None)

    if current_index is None:
        messages.error(request, "Карточка клиента не найдена.")
        return redirect("home:client_list_manage")

    target_index = current_index - 1 if direction == "up" else current_index + 1
    if not 0 <= target_index < len(ordered):
        return redirect(_safe_return(request, "home:client_list_manage"))

    ordered[current_index], ordered[target_index] = ordered[target_index], ordered[current_index]

    changed = []
    with transaction.atomic():
        for position, client in enumerate(ordered, start=1):
            new_order = position * 10
            if client.sort_order != new_order:
                client.sort_order = new_order
                changed.append(client)

        if changed:
            ClientShowcase.objects.bulk_update(changed, ("sort_order",))

    messages.success(request, "Порядок карточек изменён.")
    return redirect(_safe_return(request, "home:client_list_manage"))


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def client_reorder(request):
    raw_ids = request.POST.get("ordered_ids", "")

    try:
        ordered_ids = [int(value) for value in raw_ids.split(",") if value.strip()]
    except ValueError:
        return JsonResponse({"ok": False, "error": "Некорректный порядок карточек."}, status=400)

    current_ids = list(ClientShowcase.objects.values_list("id", flat=True))
    if len(ordered_ids) != len(current_ids) or set(ordered_ids) != set(current_ids):
        return JsonResponse(
            {"ok": False, "error": "Список карточек изменился. Обновите страницу и повторите."},
            status=409,
        )

    clients_by_id = ClientShowcase.objects.in_bulk(ordered_ids)
    changed = []

    with transaction.atomic():
        for position, client_id in enumerate(ordered_ids, start=1):
            client = clients_by_id[client_id]
            new_order = position * 10
            if client.sort_order != new_order:
                client.sort_order = new_order
                changed.append(client)

        if changed:
            ClientShowcase.objects.bulk_update(changed, ("sort_order",))

    return JsonResponse({"ok": True, "updated": len(changed)})


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def client_delete(request, client_id):
    client = get_object_or_404(ClientShowcase, pk=client_id)
    client_name = client.name

    if client.image:
        client.image.delete(save=False)

    client.delete()
    messages.success(request, f'Клиент «{client_name}» удалён.')
    return redirect(_safe_return(request, "home:client_list_manage"))


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def team_list_manage(request):
    members = TeamMember.objects.all()

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()

    if search:
        members = members.filter(Q(name__icontains=search) | Q(position__icontains=search))

    if status == "published":
        members = members.filter(is_published=True)
    elif status == "hidden":
        members = members.filter(is_published=False)

    total = members.count()
    sortable = not search and not status

    return render(
        request,
        "home/manage/team_list.html",
        {
            "members": members,
            "total": total,
            "search": search,
            "status": status,
            "sortable": sortable,
        },
    )


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def team_create(request):
    if request.method == "POST":
        form = TeamMemberForm(request.POST, request.FILES)
        if form.is_valid():
            member = form.save()
            messages.success(request, f'Сотрудник «{member.name}» добавлен.')
            return redirect("home:team_list_manage")
    else:
        next_order = (TeamMember.objects.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0) + 10
        form = TeamMemberForm(initial={"sort_order": next_order, "is_published": True})

    return render(request, "home/manage/team_form.html", {"form": form, "title": "Добавить сотрудника"})


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def team_edit(request, member_id):
    member = get_object_or_404(TeamMember, pk=member_id)

    if request.method == "POST":
        form = TeamMemberForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, f'Сотрудник «{member.name}» обновлён.')
            return redirect("home:team_list_manage")
    else:
        form = TeamMemberForm(instance=member)

    return render(request, "home/manage/team_form.html", {"form": form, "member": member, "title": "Редактировать сотрудника"})


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def team_toggle_published(request, member_id):
    member = get_object_or_404(TeamMember, pk=member_id)
    member.is_published = not member.is_published
    member.save(update_fields=("is_published", "updated_at"))
    state = "опубликован" if member.is_published else "снят с публикации"
    messages.success(request, f'Сотрудник «{member.name}» {state}.')
    return redirect(_safe_return(request, "home:team_list_manage"))


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def team_move(request, member_id):
    direction = request.POST.get("direction")
    if direction not in {"up", "down"}:
        messages.error(request, "Некорректное направление перемещения.")
        return redirect("home:team_list_manage")

    ordered = list(TeamMember.objects.order_by("sort_order", "id"))
    current_index = next((i for i, item in enumerate(ordered) if item.pk == member_id), None)
    if current_index is None:
        messages.error(request, "Сотрудник не найден.")
        return redirect("home:team_list_manage")

    target_index = current_index - 1 if direction == "up" else current_index + 1
    if not 0 <= target_index < len(ordered):
        return redirect(_safe_return(request, "home:team_list_manage"))

    ordered[current_index], ordered[target_index] = ordered[target_index], ordered[current_index]
    changed = []
    with transaction.atomic():
        for position, member in enumerate(ordered, start=1):
            new_order = position * 10
            if member.sort_order != new_order:
                member.sort_order = new_order
                changed.append(member)
        if changed:
            TeamMember.objects.bulk_update(changed, ("sort_order",))

    messages.success(request, "Порядок сотрудников изменён.")
    return redirect(_safe_return(request, "home:team_list_manage"))


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def team_reorder(request):
    raw_ids = request.POST.get("ordered_ids", "")
    try:
        ordered_ids = [int(value) for value in raw_ids.split(",") if value.strip()]
    except ValueError:
        return JsonResponse({"ok": False, "error": "Некорректный порядок сотрудников."}, status=400)

    current_ids = list(TeamMember.objects.values_list("id", flat=True))
    if len(ordered_ids) != len(current_ids) or set(ordered_ids) != set(current_ids):
        return JsonResponse({"ok": False, "error": "Список сотрудников изменился. Обновите страницу и повторите."}, status=409)

    members_by_id = TeamMember.objects.in_bulk(ordered_ids)
    changed = []
    with transaction.atomic():
        for position, member_id in enumerate(ordered_ids, start=1):
            member = members_by_id[member_id]
            new_order = position * 10
            if member.sort_order != new_order:
                member.sort_order = new_order
                changed.append(member)
        if changed:
            TeamMember.objects.bulk_update(changed, ("sort_order",))

    return JsonResponse({"ok": True, "updated": len(changed)})


@require_POST
@role_required(ROLE_MANAGER, ROLE_ADMIN)
def team_delete(request, member_id):
    member = get_object_or_404(TeamMember, pk=member_id)
    name = member.name
    if member.image:
        member.image.delete(save=False)
    member.delete()
    messages.success(request, f'Сотрудник «{name}» удалён.')
    return redirect(_safe_return(request, "home:team_list_manage"))


@role_required(ROLE_MANAGER, ROLE_ADMIN)
def contacts_manage(request):
    contacts = ContactSettings.objects.filter(pk=1).first()
    if contacts is None:
        contacts = ContactSettings(pk=1, is_published=False)

    if request.method == "POST":
        form = ContactSettingsForm(request.POST, instance=contacts)
        if form.is_valid():
            form.save()
            messages.success(request, "Контактные данные обновлены.")
            return redirect("home:contacts_manage")
    else:
        form = ContactSettingsForm(instance=contacts)

    return render(
        request,
        "home/manage/contacts_form.html",
        {"form": form, "contacts": contacts},
    )
