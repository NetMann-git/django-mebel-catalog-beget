"""Subject-specific presentation mapping; service data is unchanged."""
from django import template
register = template.Library()
SERVICE_ICONS = {'Мебель под лестницей': 'stairs', 'Мебель для мансард': 'roof', 'Гардеробные комнаты': 'wardrobe', 'Кухни и кухонные гарнитуры': 'kitchen', 'Шкафы-купе и распашные шкафы': 'wardrobe', 'Детская мебель': 'kids', 'Кровати и мебель для спальни': 'bed', 'Прихожие и мебель для дома': 'home', 'Деревянные лестницы': 'stairs', 'Межкомнатные двери из массива': 'door', 'Мебель из массива': 'countertop', 'Мебельные фасады из массива': 'panels', 'Декоративные деревянные элементы': 'panels', 'Эксклюзивные столярные изделия': 'carving', 'Прилавки и стойки для магазинов': 'reception', 'Торговые полки, стеллажи и витрины': 'shelving', 'Мебель для коммерческих помещений': 'office', 'Мебель для гостиниц и отелей': 'hotel', 'Подоконники': 'window', 'Столешницы': 'countertop', 'По вашим размерам, чертежам и образцам': 'design'}
GROUP_ICONS = {'storage':'wardrobe','wood':'wood','business':'store','surfaces':'countertop','individual':'design'}

@register.filter
def service_icon(title):
    return SERVICE_ICONS.get(title, 'design')

@register.filter
def group_icon(key):
    return GROUP_ICONS.get(key, 'design')
