import os

from ckeditor.fields import RichTextField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


class Tag(models.Model):
    name = models.CharField(max_length=50, verbose_name="Название тега")

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"

    def __str__(self):
        return self.name


class PostManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status="published")


class Post(models.Model):
    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("published", "Опубликовано"),
    ]

    title = models.CharField(max_length=250, verbose_name="Заголовок")
    slug = models.SlugField(
        max_length=250,
        unique_for_date="publish",
        verbose_name="URL-адрес",
        unique=True,
        blank=True,  # Разрешаем пустое значение для автозаполнения
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
        verbose_name="Автор",
    )
    body = RichTextField(verbose_name="Содержание")
    publish = models.DateTimeField(default=timezone.now, verbose_name="Дата публикации")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="draft", verbose_name="Статус"
    )
    tags = models.ManyToManyField(
        "Tag", related_name="posts", through="PostTag", verbose_name="Теги", blank=True
    )
    image = models.ImageField(
        upload_to="post_images/", verbose_name="Изображение", blank=True, null=True
    )

    objects = models.Manager()  # Менеджер по умолчанию
    published = PostManager()  # Кастомный менеджер для опубликованных постов

    class Meta:
        ordering = ["-publish"]
        indexes = [
            models.Index(fields=["-publish"]),
        ]
        verbose_name = "Пост"
        verbose_name_plural = "Посты"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("post_detail", args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        original_slug = slugify(self.title)
        queryset = Post.objects.all()
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)

        count = 1
        slug = original_slug
        while queryset.filter(slug=slug).exists():
            slug = f"{original_slug}-{count}"
            count += 1

        return slug

    @classmethod
    def filter_posts_by_title(cls, keyword):
        return cls.objects.filter(title__icontains=keyword)

    @classmethod
    def filter_posts_by_status_and_title(cls, status, keyword):
        return cls.objects.filter(status=status).filter(title__icontains=keyword)

    @classmethod
    def update_post_status(cls, post_id, new_status):
        return cls.objects.filter(id=post_id).update(status=new_status)

    @classmethod
    def delete_post_by_id(cls, post_id):
        return cls.objects.filter(id=post_id).delete()

    @classmethod
    def get_post_values(cls):
        return cls.objects.values("title", "author__username")

    @classmethod
    def get_post_values_list(cls):
        return cls.objects.values_list("title", "author__username")

    @classmethod
    def count_posts(cls):
        return cls.objects.count()

    @classmethod
    def check_post_exists(cls, post_id):
        return cls.objects.filter(id=post_id).exists()

    @classmethod
    def get_latest_posts(cls, limit=5):
        return cls.published.order_by("-publish")[:limit]

    @classmethod
    def get_posts_per_author(cls):
        return (
            cls.objects.values("author__username")
            .annotate(total_posts=Count("id"))
            .order_by("-total_posts")
        )


class PostTag(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, verbose_name="Пост")
    tag = models.ForeignKey("Tag", on_delete=models.CASCADE, verbose_name="Тег")

    class Meta:
        verbose_name = "Тег поста"
        verbose_name_plural = "Теги постов"

    def __str__(self):
        return f"{self.post.title} - {self.tag.name}"


class CustomUser(AbstractUser):
    phone = models.CharField(
        _("Телефон"),
        max_length=12,
        default="+70000000000",
        help_text=_("Формат: +79991234567"),
    )
    last_name = models.CharField(_("Фамилия"), max_length=100, blank=False)
    username = models.CharField(_("Имя"), max_length=100, unique=True)

    patronymic = models.CharField(_("Отчество"), max_length=100, blank=True, null=True)

    REQUIRED_FIELDS = ["email", "phone", "last_name", "patronymic"]

    class Meta:
        db_table = "recreation_customuser"
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")
        ordering = ["last_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username

    def get_full_name(self):
        """Возвращает полное имя в формате 'Фамилия Имя Отчество'"""
        full_name = f"{self.last_name} {self.username}"  # Используем username как имя
        if self.patronymic:
            full_name += f" {self.patronymic}"
        return full_name.strip()

    def save(self, *args, **kwargs):
        # Если username не задан, используем email
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)


class Client(models.Model):
    client_id = models.AutoField(primary_key=True, verbose_name="ID клиента")
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="client_profile",
        null=True,
        blank=True,
        verbose_name="Учетная запись",
    )
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    patronymic = models.CharField(max_length=100, verbose_name="Отчество")
    phone_number = models.CharField(max_length=15, verbose_name="Номер телефона")
    email = models.EmailField(max_length=255, verbose_name="Email")
    document = models.FileField(
        upload_to="client_documents/%Y/%m/%d/",
        verbose_name="Документ",
        blank=True,
        null=True,
        help_text="Загрузите сканы документов (паспорт, водительские права и т.д.)",
    )

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.patronymic}"

    def save(self, *args, **kwargs):
        # При создании нового клиента автоматически создаём пользователя
        if not self.pk and not self.user:
            user = CustomUser.objects.create_user(
                username=self.email,  # Используем email как username
                email=self.email,
                last_name=self.last_name,
                patronymic=self.patronymic,
                phone=self.phone_number,
            )
            self.user = user
        super().save(*args, **kwargs)


class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True, verbose_name="ID сотрудника")
    position_id = models.ForeignKey(
        "Position", on_delete=models.CASCADE, verbose_name="Должность"
    )
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    patronymic = models.CharField(max_length=100, verbose_name="Отчество")
    contact_info = models.CharField(
        max_length=255, verbose_name="Контактная информация"
    )

    # Добавляем новые поля
    phone = models.CharField(
        max_length=20, verbose_name="Телефон", blank=True, null=True
    )
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    hire_date = models.DateField(verbose_name="Дата приема", blank=True, null=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.patronymic}"


class Position(models.Model):
    position_id = models.AutoField(primary_key=True, verbose_name="ID должности")
    name = models.CharField(max_length=100, verbose_name="Название должности")
    responsibilities = RichTextField(verbose_name="Обязанности")

    class Meta:
        verbose_name = "Должность"
        verbose_name_plural = "Должности"

    def __str__(self):
        return self.name


class House(models.Model):
    house_id = models.AutoField(primary_key=True, verbose_name="ID дома")
    employee_id = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ответственный сотрудник",
    )
    name = models.CharField(max_length=100, verbose_name="Название коттеджа")
    slug = models.SlugField(
        max_length=100, unique=True, blank=True, verbose_name="URL-идентификатор"
    )
    location = models.CharField(max_length=200, verbose_name="Местоположение")
    capacity = models.IntegerField(verbose_name="Вместимость (чел.)")
    price_per_night = models.IntegerField(verbose_name="Цена за ночь (руб.)")
    description = models.TextField(verbose_name="Описание", blank=True, null=True)
    amenities = models.TextField(verbose_name="Удобства", blank=True, null=True)
    image = models.ImageField(
        upload_to="houses/", verbose_name="Изображение", blank=True, null=True
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    history = HistoricalRecords()  # Добавляем историю

    @property
    def get_image_url(self):
        """Возвращает URL изображения коттеджа"""
        if self.image and hasattr(self.image, "url"):
            return self.image.url

        # Проверяем наличие изображения в медиа
        media_path = os.path.join("houses", f"{self.slug}.jpg")
        full_media_path = os.path.join(settings.MEDIA_ROOT, media_path)
        if os.path.exists(full_media_path):
            return os.path.join(settings.MEDIA_URL, media_path)

        # Проверяем наличие изображения в статике
        static_path = os.path.join("images", f"{self.slug}.jpg")
        full_static_path = os.path.join(settings.STATIC_ROOT, static_path)
        if os.path.exists(full_static_path):
            return os.path.join(settings.STATIC_URL, static_path)

        # Возвращаем изображение по умолчанию
        return os.path.join(settings.STATIC_URL, "images/no-image.jpg")

    def image_exists(self):
        """Проверяет существование файла изображения"""
        if self.image and hasattr(self.image, "url"):
            return True

        # Проверяем медиа и статику
        media_exists = os.path.exists(
            os.path.join(settings.MEDIA_ROOT, "houses", f"{self.slug}.jpg")
        )
        static_exists = os.path.exists(
            os.path.join(settings.STATIC_ROOT, "images", f"{self.slug}.jpg")
        )
        return media_exists or static_exists

    class Meta:
        verbose_name = "Коттедж"
        verbose_name_plural = "Коттеджи"


class Facility(models.Model):
    facility_id = models.AutoField(primary_key=True, verbose_name="ID оборудования")
    house_id = models.ForeignKey(
        "House", on_delete=models.CASCADE, verbose_name="Коттедж"
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    location = models.CharField(max_length=100, verbose_name="Расположение")
    description = RichTextField(verbose_name="Описание")
    status = models.CharField(max_length=50, verbose_name="Статус")

    class Meta:
        verbose_name = "Оборудование"
        verbose_name_plural = "Оборудование"

    def __str__(self):
        return self.name


class Review(models.Model):
    review_id = models.AutoField(primary_key=True, verbose_name="ID отзыва")
    client_id = models.ForeignKey(
        Client, on_delete=models.CASCADE, verbose_name="Клиент"
    )
    house_id = models.ForeignKey(
        House, on_delete=models.CASCADE, verbose_name="Коттедж"
    )
    rating = models.IntegerField(verbose_name="Рейтинг")
    comment = RichTextField(verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    @classmethod
    def get_all_reviews(cls):
        return (
            cls.objects.all()
            .select_related("client_id", "house_id")
            .order_by("-created_at")
        )

    def save(self, *args, **kwargs):
        # Очищаем текст от тегов перед сохранением
        self.comment = strip_tags(self.comment)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Отзыв от {self.client_id} для {self.house_id}"


class Service(models.Model):
    SERVICE_TYPES = [
        ("entertainment", "Развлечения"),
        ("relax", "Релакс"),
        ("transport", "Транспорт"),
        ("other", "Другое"),
    ]
    service_id = models.AutoField(primary_key=True, verbose_name="ID услуги")
    name = models.CharField(max_length=100, verbose_name="Название услуги")
    description = models.TextField(verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    quantity = models.IntegerField(verbose_name="Количество")
    image = models.ImageField(upload_to="services/", verbose_name="Изображение")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    type = models.CharField(
        max_length=20, choices=SERVICE_TYPES, verbose_name="Тип услуги"
    )

    def get_absolute_url(self):
        return f"/services/{self.pk}/"

    def __str__(self):
        return self.name

    def get_icon(self):
        return {
            "entertainment": "fa-gamepad",
            "food": "fa-utensils",
            "transport": "fa-car",
            "other": "fa-star",
        }.get(self.type, "fa-check")

    @property
    def short_description(self):
        """Сокращенное описание для превью"""
        return (
            (self.description[:100] + "...")
            if len(self.description) > 100
            else self.description
        )

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["type", "name"]


class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True, verbose_name="ID бронирования")
    client_id = models.ForeignKey(
        "Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Клиент",
    )
    house = models.ForeignKey(
        "House",
        on_delete=models.CASCADE,
        verbose_name="Коттедж",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Пользователь",
    )
    check_in_date = models.DateField(verbose_name="Дата заезда")
    check_out_date = models.DateField(verbose_name="Дата выезда")
    guests = models.PositiveIntegerField(verbose_name="Количество гостей")
    phone_number = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(verbose_name="Email")
    client_name = models.CharField(
        max_length=255,
        verbose_name="Имя клиента",
        default="Не указано",
    )
    base_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Базовая стоимость",
        default=0.00,
    )
    total_cost = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Общая стоимость", default=0.00
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    services = models.ManyToManyField(
        "Service", blank=True, verbose_name="Дополнительные услуги"
    )
    comment = RichTextField(verbose_name="Комментарий", blank=True, null=True)
    history = HistoricalRecords(excluded_fields=["total_cost"])

    @property
    def nights(self):
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return 0
    
    BOOKING_STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('confirmed', 'Подтверждено'),
        ('cancelled', 'Отменено'),
        ('completed', 'Завершено'),
    ]
    
    #booking_status = models.CharField(
    #    max_length=20, 
    #    choices=BOOKING_STATUS_CHOICES, 
    #    default='pending',
    #    verbose_name="Статус бронирования"
    #)

    def clean(self):
        # Проверяем, что все обязательные поля заполнены
        if not all([self.check_in_date, self.check_out_date, self.guests]):
            missing_fields = []
            if not self.check_in_date:
                missing_fields.append("дата заезда")
            if not self.check_out_date:
                missing_fields.append("дата выезда")
            if not self.guests:
                missing_fields.append("количество гостей")

            raise ValidationError(
                f"Не заполнены обязательные поля: {', '.join(missing_fields)}"
            )

        # Проверка house - теперь через hasattr чтобы избежать RelatedObjectDoesNotExist
        if not hasattr(self, 'house') or not self.house:
            raise ValidationError("Не указан коттедж для бронирования")

        # 1. Проверка, что дата выезда > даты заезда
        if self.check_out_date <= self.check_in_date:
            raise ValidationError("Дата выезда должна быть позже даты заезда.")

        # 2. Запрет бронирования в прошлом
        if self.check_in_date < timezone.now().date():
            raise ValidationError("Нельзя бронировать коттедж на прошедшую дату.")

        # 3. Проверяем количество гостей
        if self.guests < 1:
            raise ValidationError("Количество гостей должно быть не менее 1")

        # 4. Проверяем вместимость дома
        if hasattr(self.house, 'capacity') and self.house.capacity:
            if self.guests > self.house.capacity:
                raise ValidationError(
                    f"Количество гостей ({self.guests}) превышает вместимость коттеджа ({self.house.capacity})"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Бронирование {self.booking_id} для {self.house.name if self.house else 'неизвестного дома'}"
    
    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"


class Event(models.Model):
    event_id = models.AutoField(primary_key=True, verbose_name="ID мероприятия")
    booking_id = models.ForeignKey(
        Booking, on_delete=models.CASCADE, verbose_name="Бронирование"
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    date = models.DateField(verbose_name="Дата")
    location = RichTextField(verbose_name="Место проведения")
    image = models.ImageField(upload_to="event_images/", verbose_name="Изображение")
    event_url = models.URLField(blank=True, verbose_name="Ссылка на мероприятие")

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    def __str__(self):
        return self.name


class BookingService(models.Model):
    service_id = models.ForeignKey(
        Service, on_delete=models.CASCADE, verbose_name="Услуга"
    )
    booking_id = models.ForeignKey(
        Booking, on_delete=models.CASCADE, verbose_name="Бронирование"
    )
    booking_date = models.DateField(verbose_name="Дата бронирования")
    return_date = models.DateField(verbose_name="Дата возврата")

    class Meta:
        verbose_name = "Бронирование услуги"
        verbose_name_plural = "Бронирования услуг"

    def __str__(self):
        return f"Бронирование услуги {self.service_id} для {self.booking_id}"


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('succeeded', 'Оплачено'),
        ('canceled', 'Отменено'),
        ('waiting_for_capture', 'Ожидает подтверждения'),
        ('refunded', 'Возвращено'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('full', 'Полная оплата'),
        ('prepayment', 'Предоплата'),
    ]

    id = models.AutoField(primary_key=True, verbose_name="ID платежа")
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, verbose_name="Бронирование"
    )
    yookassa_payment_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,  # Добавьте null=True для обратной совместимости
        verbose_name="ID платежа ЮKassa"
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Сумма"
    )
    payment_type = models.CharField(
        max_length=20, 
        choices=PAYMENT_TYPE_CHOICES, 
        verbose_name="Тип оплаты"
    )
    status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES, 
        default='pending', 
        verbose_name="Статус"
    )
    payment_date = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата создания"
    )
    captured_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Дата подтверждения"
    )
    
    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        ordering = ['-payment_date']

    def __str__(self):
        return f"Платеж {self.id} - {self.amount} ₽ ({self.get_status_display()})"

    @property
    def booking_id_display(self):
        """Отображаемый ID бронирования"""
        return self.booking.booking_id if self.booking else '-'

    @property
    def payment_method_display(self):
        """Отображаемый метод платежа"""
        return self.get_payment_type_display()


User = get_user_model()