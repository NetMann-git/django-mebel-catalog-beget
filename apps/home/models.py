from django.db import models


class ClientShowcase(models.Model):
    """Карточка клиента для секции «Наши клиенты» на главной странице."""

    name = models.CharField(max_length=120, verbose_name="Имя клиента")
    vehicle = models.CharField(max_length=180, verbose_name="Автомобиль")
    image = models.ImageField(
        upload_to="home/clients/%Y/%m/",
        blank=True,
        verbose_name="Фотография",
    )
    # Kept in sync with historical migrations; public images use the image field.
    legacy_image = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        verbose_name="Старое статическое изображение",
    )
    rutube_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Ссылка на видеоотзыв Rutube",
        help_text="Оставьте пустым, если клиент не записывал видеоотзыв.",
    )
    sort_order = models.PositiveIntegerField(
        default=100,
        db_index=True,
        verbose_name="Порядок вывода",
        help_text="Чем меньше число, тем раньше карточка показывается.",
    )
    is_published = models.BooleanField(default=True, db_index=True, verbose_name="Опубликован")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Изменён")

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Клиент на главной"
        verbose_name_plural = "Клиенты на главной"

    def __str__(self):
        return f"{self.name} — {self.vehicle}"

    @property
    def has_image(self):
        return bool(self.image)

    @property
    def rutube_embed_url(self):
        """Возвращает только проверенную embed-ссылку Rutube."""
        if not self.rutube_url:
            return ""

        import re
        from urllib.parse import urlparse

        try:
            parsed = urlparse(self.rutube_url)
        except (TypeError, ValueError):
            return ""

        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"rutube.ru", "www.rutube.ru"}:
            return ""

        match = re.search(r"/(?:video|play/embed)/([0-9a-fA-F]{32})(?:/|$)", parsed.path)
        if not match:
            return ""

        return f"https://rutube.ru/play/embed/{match.group(1).lower()}/"


class TeamMember(models.Model):
    """Сотрудник для секции «Наша команда» на главной странице."""

    name = models.CharField(max_length=120, verbose_name="Имя")
    position = models.CharField(max_length=180, verbose_name="Должность")
    image = models.ImageField(
        upload_to="home/team/%Y/%m/",
        blank=True,
        verbose_name="Фотография",
    )
    legacy_image = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        verbose_name="Старое статическое изображение",
    )
    sort_order = models.PositiveIntegerField(
        default=100,
        db_index=True,
        verbose_name="Порядок вывода",
        help_text="Чем меньше число, тем раньше сотрудник показывается.",
    )
    is_published = models.BooleanField(default=True, db_index=True, verbose_name="Опубликован")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Изменён")

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Сотрудник команды"
        verbose_name_plural = "Команда"

    def __str__(self):
        return f"{self.name} — {self.position}"

    @property
    def has_image(self):
        return bool(self.image)


class ContactSettings(models.Model):
    """Контактные данные для секции «Контакты» на главной странице."""

    phone_primary = models.CharField(max_length=40, verbose_name="Основной телефон")
    phone_secondary = models.CharField(max_length=40, blank=True, verbose_name="Дополнительный телефон")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    map_url = models.URLField(max_length=700, verbose_name="Ссылка на карту Яндекс")
    telegram_url = models.URLField(max_length=500, blank=True, verbose_name="Telegram")
    vk_url = models.URLField(max_length=500, blank=True, verbose_name="ВКонтакте")
    max_url = models.URLField(max_length=500, blank=True, verbose_name="MAX")
    is_published = models.BooleanField(default=True, verbose_name="Показывать секцию на главной")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Изменено")

    class Meta:
        verbose_name = "Контакты главной страницы"
        verbose_name_plural = "Контакты главной страницы"

    def __str__(self):
        return "Контакты главной страницы"
