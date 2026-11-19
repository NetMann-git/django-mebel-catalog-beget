"""Дополнительные примеры кухонь и шкафов с полными галереями."""
from .load_furniture_examples import Command as BaseCommand, DATA


class Command(BaseCommand):
    help = 'Добавить 20 примеров кухонь и шкафов: цветная обложка и минимум семь фото в галерее.'
    data_dir = DATA.parent / 'southern_examples'
    minimum_photos = 8
    collection = '119'
