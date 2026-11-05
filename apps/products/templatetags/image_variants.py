from django import template
from apps.products.image_variants import image_variant

register = template.Library()
register.filter('image_variant', image_variant)


@register.simple_tag
def reference_crop(source, box):
    import json
    from pathlib import Path
    from django.templatetags.static import static
    from apps.products import image_variants as variants
    crops = json.loads(Path(variants.__file__).with_name('reference_image_crops.json').read_text())
    return static(crops.get(str(source) + '|' + str(box), 'products/images/image-unavailable.svg'))
