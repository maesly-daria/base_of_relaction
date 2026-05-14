import os

from ckeditor.fields import RichTextField
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from base_relaction.settings import MIN_LEGTH_PASSWORD_CONSTANT  
def my_view(request):  
    value = MIN_LEGTH_PASSWORD_CONSTANT 

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
    body = models.TextField(verbose_name="Содержание")
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
            # Генерируем slug из заголовка
            self.slug = slugify(self.title)
            
            # Если slug уже существует, добавляем число
            original_slug = self.slug
            counter = 1
            while Post.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
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


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self.create_user(email, password, **extra_fields)
    

class CustomUser(AbstractUser):
    phone = models.CharField(
        _("Телефон"),
        max_length=20,
        blank=False,
        null=False,
        unique=True,
        help_text=_("Формат: +79999999999"),
    )
    email = models.EmailField(
        _("email address"), 
        blank=False, 
        null=False, 
        unique=True
    )
    last_name = models.CharField(_("Фамилия"), max_length=100, blank=False)
    first_name = models.CharField(_("Имя"), max_length=100, blank=False)
    patronymic = models.CharField(_("Отчество"), max_length=100, blank=True, null=True)
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone', 'last_name', 'first_name']  # patronymic не обязателен

    class Meta:
        db_table = "recreation_customuser"
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")
        ordering = ["last_name", "first_name"]

    def __str__(self):
        full_name = self.get_full_name()
        if full_name and full_name.strip():
            return full_name
        elif self.email:
            return self.email
        else:
            return f"User #{self.id}"

    def get_full_name(self):
        """Возвращает полное имя в формате 'Фамилия Имя Отчество'"""
        parts = []
        if self.last_name and self.last_name.strip():
            parts.append(self.last_name.strip())
        if self.first_name and self.first_name.strip():
            parts.append(self.first_name.strip())
        if self.patronymic and self.patronymic.strip():
            parts.append(self.patronymic.strip())
        
        return " ".join(parts) if parts else ""

    def save(self, *args, **kwargs):
        # Автоматически заполняем username email'ом для совместимости
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)


class Client(models.Model):
    client_id = models.AutoField(primary_key=True, verbose_name="ID клиента")
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        #related_name="client_profile",
        blank=True,
        verbose_name="Учетная запись",
    )
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    patronymic = models.CharField(max_length=100, verbose_name="Отчество")
    phone_number = models.CharField(max_length=20, verbose_name="Номер телефона")
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
        return self.get_full_name()
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name} {self.patronymic or ''}".strip()


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

    def delete(self, *args, **kwargs):
        """Безопасное удаление - проверяем ссылки"""
        from .models import Employee
        if Employee.objects.filter(position_id=self).exists():
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f'Невозможно удалить должность "{self.name}", '
                f'так как на нее ссылаются сотрудники. '
                f'Сначала измените должности у сотрудников.'
            )
        super().delete(*args, **kwargs)

    def get_employee_count(self):
        """Количество сотрудников с этой должностью"""
        from .models import Employee
        return Employee.objects.filter(position_id=self).count()


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

    @property
    def main_image(self):
        """Возвращает главное изображение"""
        if self.image:
            return self.image
        main_img = self.images.filter(is_main=True).first()
        if main_img:
            return main_img.image
        return None
    
    def get_gallery_images(self):
        """Возвращает все изображения кроме главного"""
        return self.images.all().order_by('order')
    
    def is_available(self, check_in, check_out, exclude_booking_id=None):
        """
        Проверяет доступность дома на указанные даты
        """
        if isinstance(check_in, str):
            check_in = datetime.strptime(check_in, '%Y-%m-%d').date()
        if isinstance(check_out, str):
            check_out = datetime.strptime(check_out, '%Y-%m-%d').date()
            
        overlapping_bookings = self.booking_set.filter(
            check_in_date__lt=check_out,
            check_out_date__gt=check_in
        )
        
        if exclude_booking_id:
            overlapping_bookings = overlapping_bookings.exclude(pk=exclude_booking_id)
            
        return not overlapping_bookings.exists()


class HouseImage(models.Model):
    house = models.ForeignKey(
        House, 
        on_delete=models.CASCADE, 
        related_name='images',
        verbose_name='Коттедж'
    )
    image = models.ImageField(
        upload_to='houses/gallery/%Y/%m/%d/',
        verbose_name='Изображение'
    )
    caption = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name='Подпись'
    )
    order = models.IntegerField(
        default=0,
        verbose_name='Порядок'
    )
    is_main = models.BooleanField(
        default=False,
        verbose_name='Главное изображение'
    )
    
    class Meta:
        verbose_name = 'Изображение коттеджа'
        verbose_name_plural = 'Изображения коттеджей'
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"{self.house.name} - {self.caption or 'Изображение'}"
    

class Event(models.Model):
    event_id = models.AutoField(primary_key=True, verbose_name="ID мероприятия")
    booking_id = models.ForeignKey(
        'Booking',
        on_delete=models.SET_NULL,  
        verbose_name="Бронирование",
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    date = models.DateField(verbose_name="Дата")
    location = RichTextField(verbose_name="Место проведения")
    image = models.ImageField(
        upload_to="event_images/", 
        verbose_name="Изображение",
        blank=True,
        null=True
    )
    event_url = models.URLField(blank=True, verbose_name="Ссылка на мероприятие")

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    def __str__(self):
        return self.name


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
        on_delete=models.PROTECT,
        null=True,  # Добавляем временно
        blank=True, # Добавляем временно  
        verbose_name="Клиент",
    )
    house = models.ForeignKey(
        "House",
        on_delete=models.CASCADE,
        verbose_name="Коттедж",
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

    def clean(self):
        super().clean()
        
        if not all([self.check_in_date, self.check_out_date, self.guests, self.house]):
            missing_fields = []
            if not self.check_in_date:
                missing_fields.append("дата заезда")
            if not self.check_out_date:
                missing_fields.append("дата выезда")
            if not self.guests:
                missing_fields.append("количество гостей")
            if not self.house:
                missing_fields.append("коттедж")

            raise ValidationError(
                f"Не заполнены обязательные поля: {', '.join(missing_fields)}"
            )

        if self.check_out_date <= self.check_in_date:
            raise ValidationError("Дата выезда должна быть позже даты заезда.")

        if self.check_in_date < timezone.now().date():
            raise ValidationError("Нельзя бронировать коттедж на прошедшую дату.")

        if self.guests < 1:
            raise ValidationError("Количество гостей должно быть не менее 1")

        if hasattr(self.house, 'capacity') and self.house.capacity:
            if self.guests > self.house.capacity:
                raise ValidationError(
                    f"Количество гостей ({self.guests}) превышает вместимость коттеджа ({self.house.capacity})"
                )
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверка на двойное бронирование
        if self.house and self.check_in_date and self.check_out_date:
            overlapping_bookings = Booking.objects.filter(
                house=self.house,
                check_in_date__lt=self.check_out_date,
                check_out_date__gt=self.check_in_date
            ).exclude(pk=self.pk)  # Исключаем текущее бронирование при обновлении
            
            if overlapping_bookings.exists():
                raise ValidationError(
                    f"Этот коттедж уже забронирован на выбранные даты. "
                    f"Пожалуйста, выберите другие даты."
                )

    def calculate_base_cost(self):
        """Расчет базовой стоимости проживания"""
        if not self.house or not self.check_in_date or not self.check_out_date:
            return Decimal('0')
            
        nights = (self.check_out_date - self.check_in_date).days
        if nights <= 0:
            return Decimal('0')
            
        return Decimal(str(self.house.price_per_night)) * Decimal(str(nights))
    
    def calculate_services_cost(self):
        """Расчет стоимости услуг"""
        if not self.pk:
            return Decimal('0')
        return sum(Decimal(str(service.price)) for service in self.services.all())
    
    def calculate_total_cost(self):
        """Расчет общей стоимости с учетом услуг"""
        base_cost = self.calculate_base_cost()
        services_cost = self.calculate_services_cost()
        return base_cost + services_cost

    def save(self, *args, **kwargs):
        """Сохраняем с расчетом стоимости"""
        self.full_clean()
        
        # Расчет стоимости
        self.base_cost = self.calculate_base_cost()
        
        # Для нового объекта сначала сохраняем без услуг
        if not self.pk:
            self.total_cost = self.base_cost
            super().save(*args, **kwargs)
            # После сохранения пересчитываем с услугами
            self.total_cost = self.calculate_total_cost()
            super().save(update_fields=['total_cost'])
        else:
            # Для существующего объекта полный расчет
            self.total_cost = self.calculate_total_cost()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"Бронирование {self.booking_id} для {self.house.name if self.house else 'неизвестного дома'}"
    
    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"


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


# Модели для пакетного конструктора (добавить в конец файла)
class TravelPackage(models.Model):
    PACKAGE_TYPES = [
        ('weekend', 'Выходные'),
        ('holiday', 'Праздничный'),
        ('weekday', 'Будничный'),
        ('extended', 'Продленный'),
        ('custom', 'Индивидуальный'),
    ]
    
    package_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, verbose_name="Название пакета")
    package_type = models.CharField(max_length=20, choices=PACKAGE_TYPES, verbose_name="Тип пакета")
    base_house = models.ForeignKey('House', on_delete=models.CASCADE, verbose_name="Базовый коттедж")
    duration_days = models.IntegerField(verbose_name="Длительность (дней)")
    min_guests = models.IntegerField(verbose_name="Мин. гостей")
    max_guests = models.IntegerField(verbose_name="Макс. гостей")
    description = models.TextField(verbose_name="Описание")
    base_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Базовая цена")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    image = models.ImageField(upload_to='packages/', verbose_name="Изображение", blank=True, null=True)
    
    # Новые поля для местных
    local_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Скидка для местных (%)")
    quick_booking = models.BooleanField(default=False, verbose_name="Быстрое бронирование")
    flexible_checkin = models.BooleanField(default=False, verbose_name="Гибкий заезд")
    
    class Meta:
        verbose_name = "Пакет путешествия"
        verbose_name_plural = "Пакеты путешествий"
        db_table = 'recreation_travelpackage'
    
    def __str__(self):
        return self.name
    
    def calculate_price_for_locals(self, selected_options=None):
        """Расчет стоимости для местных жителей со скидкой"""
        total = float(self.base_price) * (1 - float(self.local_discount) / 100)
        if selected_options:
            for option in selected_options:
                total += float(option.price)
        return total

    def is_available_for_dates(self, check_in, check_out):
        """Проверяет, доступен ли пакет на выбранные даты"""
        return self.base_house.is_available(check_in, check_out)
    
    def get_final_price(self, user):
        """Возвращает финальную цену с учетом скидки для местных"""
        if self._is_local_user(user):
            return float(self.base_price) * (1 - float(self.local_discount) / 100)
        return float(self.base_price)
    
    def _is_local_user(self, user):
        """Проверяет, является ли пользователь местным"""
        if not user.is_authenticated:
            return False
        try:
            client = Client.objects.get(user=user)
            return Booking.objects.filter(client_id=client).count() >= 2
        except (Client.DoesNotExist, AttributeError):
            return False


class PackageService(models.Model):
    package = models.ForeignKey('TravelPackage', on_delete=models.CASCADE)
    service = models.ForeignKey('Service', on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1, verbose_name="Количество")
    included_in_base = models.BooleanField(default=True, verbose_name="Включено в базовую стоимость")
    optional = models.BooleanField(default=False, verbose_name="Опциональная услуга")
    price_override = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Спец. цена")
    
    class Meta:
        verbose_name = "Услуга в пакете"
        verbose_name_plural = "Услуги в пакетах"
        db_table = 'recreation_packageservice'


class PackageOption(models.Model):
    OPTION_TYPES = [
        ('food', 'Питание'),
        ('activities', 'Активности'),
        ('comfort', 'Комфорт'),
        ('entertainment', 'Развлечения'),
        ('local', 'Локальные услуги'),
    ]
    
    package = models.ForeignKey('TravelPackage', on_delete=models.CASCADE, related_name='options')
    name = models.CharField(max_length=200, verbose_name="Название опции")
    option_type = models.CharField(max_length=20, choices=OPTION_TYPES, verbose_name="Тип опции")
    description = models.TextField(verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    popular_local = models.BooleanField(default=False, verbose_name="Популярно у местных")
    
    class Meta:
        verbose_name = "Опция пакета"
        verbose_name_plural = "Опции пакетов"
        db_table = 'recreation_packageoption'
    
    def __str__(self):
        return f"{self.name} ({self.get_option_type_display()})"


class CustomPackageBooking(models.Model):
    booking = models.OneToOneField('Booking', on_delete=models.CASCADE, verbose_name="Бронирование", related_name='custom_package')
    travel_package = models.ForeignKey('TravelPackage', on_delete=models.CASCADE, verbose_name="Пакет")
    selected_options = models.ManyToManyField('PackageOption', blank=True, verbose_name="Выбранные опции")
    custom_requests = models.TextField(blank=True, verbose_name="Особые пожелания")
    total_package_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Общая стоимость пакета")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Бронирование пакета"
        verbose_name_plural = "Бронирования пакетов"
        db_table = 'recreation_custompackagebooking'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        # Пересчитываем стоимость только если не установлена вручную
        if not self.total_package_price or kwargs.get('force_recalculate', False):
            options_price = sum(float(opt.price) for opt in self.selected_options.all())
            base_price = float(self.travel_package.base_price)
            self.total_package_price = base_price + options_price
        
        # Убираем force_recalculate из kwargs перед сохранением
        kwargs.pop('force_recalculate', None)
        super().save(*args, **kwargs)
    
    def get_final_price(self, user=None):
        """Получить финальную цену с учетом скидок для местных"""
        base_price = float(self.total_package_price)
        
        if user and hasattr(user, 'is_local') and user.is_local:
            discount = getattr(self.travel_package, 'local_discount', 0)
            if discount:
                return base_price * (1 - discount / 100)
        
        return base_price
    
    def get_included_services(self):
        """Получить все услуги, включенные в пакет"""
        return self.travel_package.options.all()
    
    def get_selected_options_list(self):
        """Получить список выбранных опций"""
        return self.selected_options.all()
    
    def __str__(self):
        return f"Пакетное бронирование #{self.booking.booking_id} - {self.travel_package.name}"


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