"""Категории из согласованного мебельного макета, без изменения старых данных."""
from urllib.parse import urlencode
from django.urls import reverse
from .models import Category

FURNITURE_CATEGORIES = (
    ("shkafy", "Шкафы"),
    ("kuhni", "Кухни"),
    ("stellazhi", "Стеллажи"),
    ("polki", "Полки"),
    ("garderobnye", "Гардеробные"),
    ("drugaya-mebel", "Другая мебель"),
)


def category_plan(rows):
    """Не исправлять вручную созданные названия и URL автоматически."""
    def key(value):
        return value.strip().casefold()
    result = []
    for slug, title in FURNITURE_CATEGORIES:
        candidates = [row for row in rows
                      if key(row["slug"]) == key(slug) or key(row["title"]) == key(title)]
        exact = [row for row in candidates if row["slug"] == slug and row["title"] == title]
        action = "skip" if len(candidates) == len(exact) == 1 else ("conflict" if candidates else "create")
        result.append({"slug": slug, "title": title, "action": action, "existing": candidates})
    return result


def furniture_category_urls():
    """Не направлять посетителя в случайную категорию при конфликте справочника."""
    rows = list(Category.objects.values("pk", "title", "slug").order_by("pk"))
    return {
        item["slug"].replace("-", "_"): reverse("catalog:catalog") + "?" + urlencode({"category": item["existing"][0]["pk"]})
        for item in category_plan(rows) if item["action"] == "skip"
    }
