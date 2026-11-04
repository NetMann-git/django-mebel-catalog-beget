# apps/home/views.py

from django.shortcuts import render

from .context import HomeContextBuilder


def home(request):
    context = HomeContextBuilder.build(request)
    return render(request, "home/home.html", context)


def services(request):
    from .services_content import SERVICE_GROUPS
    return render(request, "home/services.html", {"service_groups": SERVICE_GROUPS})
