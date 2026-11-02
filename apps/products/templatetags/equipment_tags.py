"""Render only selected, active equipment without affecting attributes."""
from django import template
from apps.products.models import Product

register = template.Library()


@register.inclusion_tag('products/equipment/public.html')
def vehicle_equipment(product: Product, furniture=False) -> dict:
    """Build groups only when they contain selected visible options."""
    groups = {}
    for option in product.equipment.filter(is_active=True).select_related('group'):
        if option.group_id not in groups:
            groups[option.group_id] = (option.group.name, [])
        groups[option.group_id][1].append(option)
    return {'equipment_groups': list(groups.values()), 'furniture': furniture}
