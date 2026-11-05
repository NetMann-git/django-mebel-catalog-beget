"""Browser fallback URLs; assets are served by the configured static storage."""
from django.http import HttpResponsePermanentRedirect
from django.templatetags.static import static


def branding_icon(request, filename):
    return HttpResponsePermanentRedirect(static('home/branding/' + filename))
