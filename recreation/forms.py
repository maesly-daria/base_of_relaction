import re

import django_filters
from ckeditor.widgets import CKEditorWidget
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .models import Booking, Client, CustomUser, House, Post, Review, Service

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(required=True, label="Номер телефона")
    last_name = forms.CharField(required=True, label="Фамилия")
    username = forms.CharField(required=True, label="Имя")
    patronymic = forms.CharField(required=False, label="Отчество")

    class Meta:
        model = CustomUser
        fields = (
            "username",
            "email",
            "phone",
            "last_name",
            "patronymic",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        # Сохраняем все данные в модель пользователя
        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data["phone"]
        user.last_name = self.cleaned_data["last_name"]
        user.patronymic = self.cleaned_data.get("patronymic", "")

        if commit:
            user.save()
            # Создаем профиль клиента
            Client.objects.create(
                user=user,
                last_name=user.last_name,
                first_name=user.username,  # Используем username как имя
                patronymic=user.patronymic,
                phone_number=user.phone,
                email=user.email,
            )
        return user


class CustomUserChangeForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=12,
        required=True,
        label="Телефон",
        widget=forms.TextInput(
            attrs={"placeholder": "+7 (___) ___-__-__", "class": "phone-input"}
        ),
        help_text="Формат: +7 (XXX) XXX-XX-XX",
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        label="Фамилия",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    username = forms.CharField(
        max_length=100,
        required=True,
        label="Имя",  # Убедитесь, что здесь label="Имя"
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    patronymic = forms.CharField(
        max_length=100,
        required=False,
        label="Отчество",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = CustomUser
        fields = ("username", "last_name", "patronymic", "email", "phone")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "patronymic": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        # Очищаем номер от всех нецифровых символов
        cleaned_phone = re.sub(r"\D", "", phone)
        if len(cleaned_phone) != 11:
            raise forms.ValidationError("Номер должен содержать 11 цифр")
        if not phone.startswith("+7"):
            raise ValidationError("Телефон должен начинаться с +7")
        return f"+7{cleaned_phone[1:]}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True  # Email нельзя менять


class EmailPhoneAuthForm(AuthenticationForm):
    username = forms.CharField(label="Email или телефон")


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["phone_number"]  # Остальные поля теперь в форме пользователя

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Скрываем поля, которые теперь в форме пользователя
        for field_name in ["last_name", "first_name", "patronymic", "email"]:
            if field_name in self.fields:
                self.fields.pop(field_name)


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["house_id", "rating", "comment"]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 3}),
            "rating": forms.Select(choices=[(i, i) for i in range(1, 6)]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["house_id"].queryset = House.objects.filter(is_active=True)


class LoginForm(forms.Form):
    username = forms.CharField(label="Email или телефон")
    password = forms.CharField(widget=forms.PasswordInput)


class PostForm(forms.ModelForm):
    body = forms.CharField(widget=CKEditorWidget())

    class Meta:
        model = Post
        fields = ["title", "slug", "body", "status", "tags", "image"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "tags": forms.SelectMultiple(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "title": "Заголовок",
            "slug": "Слаг",
            "body": "Текст",
            "status": "Статус",
            "image": "Изображение",
        }
        help_texts = {
            "slug": "Уникальный идентификатор для URL.",
        }
        error_messages = {
            "title": {
                "required": "Это поле обязательно.",
            },
        }

    class Media:
        css = {"all": ("styles.css",)}
        js = ("script.js",)

    def save(self, commit=True, user=None):
        post = super().save(commit=False)
        if user:
            post.author = user  # Привязываем текущего пользователя
        if commit:
            post.save()
        return post

    def clean_title(self):
        title = self.cleaned_data.get("title")
        if not title:
            raise forms.ValidationError("Title is required.")
        return title


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Email или телефон")


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "last_name",
            "first_name",
            "patronymic",
            "email",
            "phone_number",
            "document",
        ]
        widgets = {
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "patronymic": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "last_name": "Фамилия",
            "first_name": "Имя",
            "patronymic": "Отчество",
            "email": "Email",
            "phone_number": "Телефон",
            "document": "Документ",
        }
        help_texts = {
            "email": "Введите действительный адрес электронной почты.",
        }
        error_messages = {
            "email": {
                "invalid": "Введите правильный адрес электронной почты.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True  # Запрещаем изменение email

    def clean_email(self):
        # Проверка, что email не изменялся
        if self.instance and self.instance.email != self.cleaned_data["email"]:
            raise forms.ValidationError("Вы не можете изменить email")
        return self.cleaned_data["email"]

    def clean_document(self):
        document = self.cleaned_data.get("document")
        if document:
            # Проверка размера файла (5MB)
            if document.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Файл слишком большой (максимум 5MB)")
            # Проверка расширения файла
            valid_extensions = [".pdf", ".jpg", ".jpeg", ".png"]
            if not any(document.name.lower().endswith(ext) for ext in valid_extensions):
                raise forms.ValidationError(
                    "Поддерживаются только PDF, JPG и PNG файлы"
                )
        return document


class HouseForm(forms.ModelForm):
    class Meta:
        model = House
        fields = "__all__"
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control"}),
            "price_per_night": forms.NumberInput(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "name": "Название",
            "location": "Местоположение",
            "capacity": "Вместимость",
            "price_per_night": "Цена за ночь",
            "image": "Изображение",
        }
        help_texts = {
            "capacity": "Максимальное количество гостей.",
        }
        error_messages = {
            "price_per_night": {
                "required": "Это поле обязательно.",
            },
        }


class BookingForm(forms.ModelForm):
    client_name = forms.CharField(
        label="ФИО",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone_number = forms.CharField(
        label="Телефон",
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        validators=[RegexValidator(regex=r"^\+7\d{10}$")],
    )

    check_in_date = forms.DateField(widget=forms.HiddenInput())
    check_out_date = forms.DateField(widget=forms.HiddenInput())
    guests = forms.IntegerField(widget=forms.HiddenInput())

    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    
    class Meta:
        model = Booking
        fields = ["client_name", "email", "phone_number", "services", "comment", 
                 "check_in_date", "check_out_date", "guests"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.house = kwargs.pop("house", None)
        super().__init__(*args, **kwargs)

        if self.user and self.user.is_authenticated:
            self.fields["client_name"].initial = self.user.get_full_name()
            self.fields["email"].initial = self.user.email
            if hasattr(self.user, "phone"):
                self.fields["phone_number"].initial = self.user.phone

    def clean(self):
        cleaned_data = super().clean()

        # Проверяем что house передан
        if not self.house:
            raise ValidationError("Не указан коттедж для бронирования")

        # Проверяем что даты переданы
        check_in_date = cleaned_data.get("check_in_date")
        check_out_date = cleaned_data.get("check_out_date")
        guests = cleaned_data.get("guests")

        if not all([check_in_date, check_out_date, guests]):
            missing = []
            if not check_in_date:
                missing.append("дата заезда")
            if not check_out_date:
                missing.append("дата выезда")
            if not guests:
                missing.append("количество гостей")
            raise ValidationError(f"Не заполнены: {', '.join(missing)}")

        # Проверяем количество гостей
        if guests < 1:
            raise ValidationError("Количество гостей должно быть не менее 1")

        # Проверка вместимости
        if self.house and self.house.capacity and guests > self.house.capacity:
            raise ValidationError(
                f"Коттедж вмещает максимум {self.house.capacity} гостей"
            )

        return cleaned_data

    def save(self, commit=True):
        # Создаем экземпляр бронирования, но пока не сохраняем в базу (commit=False)
        booking = super().save(commit=False)

        # Устанавливаем дополнительные поля, которые не входят в форму
        booking.user = self.user
        booking.house = self.house

        # Получаем даты и количество гостей из cleaned_data
        booking.check_in_date = self.cleaned_data["check_in_date"]
        booking.check_out_date = self.cleaned_data["check_out_date"]
        booking.guests = self.cleaned_data["guests"]

        # Рассчитываем стоимость
        nights = (booking.check_out_date - booking.check_in_date).days
        booking.total_cost = self.house.price_per_night * nights

        # Если нужно сохранить (по умолчанию True)
        if commit:
            booking.save()  # Сначала сохраняем основную модель
            self.save_m2m()  # Затем сохраняем many-to-many отношения (услуги)

        return booking


class ClientRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=True)
    username = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    patronymic = forms.CharField(max_length=100, required=False)

    class Meta:
        model = CustomUser
        fields = (
            "last_name",
            "username",
            "patronymic",
            "email",
            "phone",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
            Client.objects.create(
                user=user,
                last_name=self.cleaned_data["last_name"],
                username=self.cleaned_data["username"],
                patronymic=self.cleaned_data.get("patronymic", ""),
                phone_number=self.cleaned_data["phone"],
                email=self.cleaned_data["email"],
            )
        return user


UserProfileForm = ClientProfileForm


class HouseFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(
        field_name="price_per_night", lookup_expr="gte"
    )
    max_price = django_filters.NumberFilter(
        field_name="price_per_night", lookup_expr="lte"
    )
    min_capacity = django_filters.NumberFilter(field_name="capacity", lookup_expr="gte")
    name_contains = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains"
    )
    has_location = django_filters.BooleanFilter(
        field_name="location", lookup_expr="isnull", exclude=True
    )

    class Meta:
        model = House
        fields = []  # Отключаем автоматические фильтры
