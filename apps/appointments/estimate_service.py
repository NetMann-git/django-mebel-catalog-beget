"""One atomic save path for full estimate requests and private attachments."""
from django.db import transaction
from .models import CallbackReferencePhoto


def save_estimate(form, *, product=None, source='site_callback', notify):
    inquiry = form.save(commit=False)
    inquiry.product = product
    inquiry.source = source
    with transaction.atomic():
        inquiry.save()
        if photo := form.cleaned_data.get('reference_photo'):
            CallbackReferencePhoto.objects.create(callback=inquiry, content=photo)
    notify(inquiry)
    return inquiry
