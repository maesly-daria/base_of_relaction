import re
from django import forms
from django.conf import settings
import django_filters
from ckeditor.widgets import CKEditorWidget
from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .models import Booking, Client, CustomUser, House, Post, Review, Service, PackageOption
from base_relaction.settings import MIN_LEGTH_PASSWORD_CONSTANT  
def my_view(request):  
    value = MIN_LEGTH_PASSWORD_CONSTANT 
User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(
        max_length=20, 
        required=True, 
        label="Номер телефона",
        widget=forms.TextInput(attrs={
            "placeholder": "+79999999999",
            "class": "form-control phone-input"
        })
    )
    last_name = forms.CharField(required=True, label="Фамилия")
    first_name = forms.CharField(required=True, label="Имя")
    patronymic = forms.CharField(required=False, label="Отчество")

    class Meta:
        model = CustomUser
        fields = (
            "first_name",
            "last_name",
            "patronymic", 
            "email",
            "phone",
            "password1",
            "password2",
        )

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not phone:
            raise forms.ValidationError("Это поле обязательно.")
        
        cleaned_phone = re.sub(r'\D', '', phone)
        
        if len(cleaned_phone) != 11:
            raise forms.ValidationError("Номер телефона должен содержать 11 цифр")
        
        if not cleaned_phone.startswith(('7', '8')):
            raise forms.ValidationError("Номер должен начинаться с 7 или 8")
        
        return '+7' + cleaned_phone[1:]


class CustomUserChangeForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=20,
        required=True,
        label="Телефон",
        widget=forms.TextInput(attrs={
            "placeholder": "+79999999999", 
            "class": "phone-input"
        }),
        help_text="Формат: +79999999999",
    )

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "patronymic", "email", "phone")

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        cleaned_phone = re.sub(r'\D', '', phone)
        
        if len(cleaned_phone) != 11:
            raise forms.ValidationError("Номер должен содержать 11 цифр")
        
        if not cleaned_phone.startswith(('7', '8')):
            raise forms.ValidationError("Телефон должен начинаться с 7 или 8")
        
        return '+7' + cleaned_phone[1:]


class EmailPhoneAuthForm(AuthenticationForm):
    username = forms.CharField(label="Email или телефон")
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Пытаемся найти пользователя по email или телефону
            user = None
            if '@' in username:
                # Если введен email
                try:
                    user = CustomUser.objects.get(email=username)
                except CustomUser.DoesNotExist:
                    pass
            else:
                # Если введен телефон
                try:
                    user = CustomUser.objects.get(phone=username)
                except CustomUser.DoesNotExist:
                    pass
            
            if user is None:
                raise forms.ValidationError("Неверный email/телефон или пароль")
            
            self.user_cache = authenticate(self.request, username=user.email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Неверный email/телефон или пароль")
            
        return self.cleaned_data


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
    # body = forms.CharField(widget=CKEditorWidget())

    class Meta:
        model = Post
        fields = ["title", "slug", "body", "status", "tags", "image"]
        widgets = {
            'body': forms.Textarea(attrs={
                'rows': 8,
                'class': 'form-control',
                'placeholder': 'Введите текст поста...'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите заголовок...'
            }),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
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
            "phone_number": forms.TextInput(attrs={
                "class": "form-control phone-input",
                "placeholder": "+79999999999"
            }),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if not phone:
            raise forms.ValidationError("Это поле обязательно.")
        
        # Очищаем от всех символов кроме цифр
        cleaned_phone = re.sub(r'\D', '', phone)
        
        # Проверяем длину
        if len(cleaned_phone) != 11:
            raise forms.ValidationError("Номер телефона должен содержать 11 цифр")
        
        # Проверяем, что номер начинается с 7 или 8
        if not cleaned_phone.startswith(('7', '8')):
            raise forms.ValidationError("Номер должен начинаться с 7 или 8")
        
        # Сохраняем в формате +7XXXXXXXXXX
        return '+7' + cleaned_phone[1:]


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
        widget=forms.TextInput(attrs={
            "class": "form-control", 
            "id": "id_phone_number",
            "placeholder": "+7 (___) ___-__-__"
        }),
    )
    
    # Добавляем поле для услуг если нужно
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Дополнительные услуги"
    )

    class Meta:
        model = Booking
        fields = [
            'house',
            'check_in_date', 
            'check_out_date',
            'guests',
            'phone_number',
            'email',
            'client_name',
            'comment',
            'services'
        ]
        widgets = {
            'check_in_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control',
                'readonly': 'readonly'
            }),
            'check_out_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control',
                'readonly': 'readonly'
            }),
            'guests': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': 1,
                'readonly': 'readonly'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Дополнительные пожелания...'
            }),
            'house': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.disable_date_validation = kwargs.pop('disable_date_validation', False)
        super().__init__(*args, **kwargs)
        # Делаем поле house скрытым
        self.fields['house'].widget = forms.HiddenInput()
    
    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        
        # Убираем все не-цифры для проверки
        cleaned_phone = re.sub(r'\D', '', phone)
        
        # Проверяем длину (11 цифр)
        if len(cleaned_phone) != 11:
            raise forms.ValidationError("Номер телефона должен содержать 11 цифр")
        
        # Проверяем, что номер начинается с 7
        if not cleaned_phone.startswith('7'):
            raise forms.ValidationError("Номер должен начинаться с 7")
        
        # Форматируем номер для сохранения
        formatted_phone = f"+7 ({cleaned_phone[1:4]}) {cleaned_phone[4:7]}-{cleaned_phone[7:9]}-{cleaned_phone[9:11]}"
        return formatted_phone

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in_date')
        check_out = cleaned_data.get('check_out_date')
        house = cleaned_data.get('house')
        
        # Проверка дат
        if check_in and check_out and check_out <= check_in:
            raise forms.ValidationError("Дата выезда должна быть позже даты заезда")
        
        # Проверка доступности дома (только если не отключена для пакетов)
        if not self.disable_date_validation and house and check_in and check_out:
            if not house.is_available(check_in, check_out):
                raise forms.ValidationError("Этот коттедж уже забронирован на выбранные даты. Пожалуйста, выберите другие даты.")
        
        return cleaned_data
   

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

class PaymentMethodForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Безопасное получение настроек с значениями по умолчанию
        prepayment_percent = getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)
        refund_days = getattr(settings, 'BOOKING_REFUND_DAYS', 3)
        
        self.fields['payment_method'] = forms.ChoiceField(
            choices=[
                ('full', 'Полная оплата онлайн - безопасная оплата через ЮKassa'),
                ('prepayment', f'Предоплата {prepayment_percent}% - оплата части стоимости онлайн'),
            ],
            widget=forms.RadioSelect,
            label='Выберите способ оплаты',
            initial='full'
        )
        
        self.fields['agree_with_terms'] = forms.BooleanField(
            required=True,
            label=f'Я согласен с условиями бронирования и понимаю, что возврат средств возможен только при отмене бронирования за {refund_days}+ суток до заезда'
        )

class AccountProfileForm(forms.ModelForm):
    # Добавляем поле телефона из CustomUser
    phone = forms.CharField(
        max_length=20,
        required=True,
        label="Телефон",
        widget=forms.TextInput(attrs={
            "class": "form-control phone-input",
            "placeholder": "+79999999999"
        })
    )
    
    class Meta:
        model = Client
        fields = [
            "last_name",
            "first_name", 
            "patronymic",
            "document",
        ]
        widgets = {
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "patronymic": forms.TextInput(attrs={"class": "form-control"}),
            "document": forms.ClearableFileInput(attrs={
                "class": "custom-file-input",
                "accept": ".pdf,.jpg,.jpeg,.png,.doc,.docx"
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Предзаполняем данными из пользователя
        if self.user:
            self.fields['phone'].initial = self.user.phone

    def save(self, commit=True):
        client = super().save(commit=False)
        
        # Обновляем данные пользователя
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.patronymic = self.cleaned_data['patronymic']
            self.user.phone = self.cleaned_data['phone']
            self.user.save()
        
        if commit:
            client.save()
        return client
    

# Формы для пакетного конструктора (добавить в конец файла)
class LocalPackageBuilderForm(forms.Form):
    OCCASION_CHOICES = [
        ('weekend', 'Выходные'),
        ('birthday', 'День рождения'),
        ('anniversary', 'Годовщина'), 
        ('family', 'Семейный отдых'),
        ('friends', 'Встреча с друзьями'),
        ('romantic', 'Романтический вечер'),
        ('none', 'Просто отдохнуть'),
    ]
    
    occasion = forms.ChoiceField(
        choices=OCCASION_CHOICES,
        label="Повод для отдыха",
        widget=forms.RadioSelect
    )
    guests = forms.IntegerField(
        min_value=1,
        max_value=20,
        label="Количество гостей",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    nights = forms.ChoiceField(
        choices=[(1, '1 ночь'), (2, '2 ночи'), (3, '3 ночи'), (4, '4+ ночей')],
        label="Количество ночей",
        widget=forms.RadioSelect
    )


class PackageCustomizationForm(forms.Form):
    selected_options = forms.ModelMultipleChoiceField(
        queryset=PackageOption.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Дополнительные опции"
    )
    custom_requests = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Особые пожелания, аллергии, предпочтения...',
            'class': 'form-control'
        }),
        required=False,
        label="Особые пожелания"
    )
    
    def __init__(self, *args, **kwargs):
        package = kwargs.pop('package', None)
        super().__init__(*args, **kwargs)
        if package:
            self.fields['selected_options'].queryset = PackageOption.objects.filter(
                package=package, 
                is_active=True
            )


class QuickBookingForm(forms.Form):
    """Форма для быстрого бронирования местными"""
    house = forms.ModelChoiceField(
        queryset=House.objects.filter(is_active=True),
        label="Коттедж",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    check_in = forms.DateField(
        label="Дата заезда",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    nights = forms.IntegerField(
        min_value=1,
        max_value=7,
        initial=2,
        label="Количество ночей",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    guests = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=2,
        label="Гости",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )