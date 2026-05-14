from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export import fields, resources
from import_export.admin import ExportMixin
from import_export.formats import base_formats
from weasyprint import CSS, HTML

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import (
    Booking,
    BookingService,
    Client,
    CustomUser,
    Employee,
    # Event,
    Facility,
    HouseImage,
    House,
    Payment,
    Position,
    Post,
    PostTag,
    Review,
    Service,
    Tag,
    PackageService,
    PackageOption,
    TravelPackage,
    CustomPackageBooking,
)

admin.site.site_header = _('Администрирование базы отдыха "FurTree"')
admin.site.site_title = _("База отдыха")
admin.site.index_title = _("Управление базой отдыха")


class BaseResource(resources.ModelResource):
    def get_export_headers(self):
        return [field.column_name for field in self.get_export_fields()]


class BaseExportAdmin(ExportMixin, admin.ModelAdmin):
    def get_export_formats(self):
        return [CustomXLSXFormat]

    def get_export_filename(self, request, queryset, file_format):
        model_name = self.model._meta.verbose_name_plural
        return f"{model_name}_export_{timezone.now().strftime('%Y-%m-%d')}.xlsx"


class CustomXLSXFormat(base_formats.XLSX):
    def get_content_type(self):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = (
        "id",
        "get_full_name", 
        "email",
        "phone",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("first_name", "last_name", "email", "phone", "patronymic")
    ordering = ("last_name", "first_name")
    
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Персональная информация", 
            {"fields": ("first_name", "last_name", "patronymic", "phone")}
        ),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}
        ),
        (
            "Важные даты", 
            {"fields": ("last_login", "date_joined"), "classes": ("collapse",)}
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "first_name",
                    "last_name", 
                    "patronymic",
                    "email",
                    "phone",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @admin.display(description="ФИО")
    def get_full_name(self, obj):
        return obj.get_full_name()
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = (
        "id",
        "get_full_name", 
        "email",
        "phone",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("first_name", "last_name", "email", "phone", "patronymic")
    ordering = ("last_name", "first_name")
    
    # ТОЛЬКО ДЛЯ ПРОСМОТРА - запрещаем редактирование
    fieldsets = (
        (None, {"fields": ("email",)}),
        (
            "Персональная информация", 
            {"fields": ("first_name", "last_name", "patronymic", "phone")}
        ),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser")}
        ),
        (
            "Важные даты", 
            {"fields": ("last_login", "date_joined"), "classes": ("collapse",)}
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "first_name",
                    "last_name", 
                    "patronymic",
                    "email",
                    "phone",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    # КРИТИЧЕСКИ ВАЖНО: Запрещаем изменение существующих записей
    def has_change_permission(self, request, obj=None):
        # Разрешаем изменение только при создании нового пользователя
        if obj is None:  # Это форма добавления
            return True
        return False  # Запрещаем редактирование существующих
    
    # Разрешаем только добавление и удаление
    def has_add_permission(self, request):
        return True
        
    def has_delete_permission(self, request, obj=None):
        return True

    @admin.display(description="ФИО")
    def get_full_name(self, obj):
        return obj.get_full_name()

admin.site.register(CustomUser, CustomUserAdmin)


class PostTagInline(admin.TabularInline):
    model = PostTag
    extra = 1
    verbose_name = _("Тег")
    verbose_name_plural = _("Теги")


class PostResource(resources.ModelResource):
    title = fields.Field(column_name="Заголовок", attribute="title")
    author = fields.Field(column_name="Автор", attribute="author")
    status = fields.Field(column_name="Статус", attribute="status")
    publish = fields.Field(column_name="Опубликовано", attribute="publish")

    class Meta:
        model = Post
        fields = ("id", "title", "author", "status", "publish")
        export_order = fields
        verbose_name_rus = "Посты"

    def get_export_queryset(self, request):
        """Кастомизация queryset для экспорта"""
        qs = super().get_export_queryset(request)
        return qs.filter(is_active=True).select_related("employee_id")

    def dehydrate_status(self, obj):
        """Кастомизация отображения статуса"""
        return "Активен" if obj.is_active else "Неактивен"

    def get_export_filename(self, request, queryset, file_format):
        """Кастомизация имени файла"""
        return f"houses_export_{timezone.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"


@admin.register(Post)
class PostAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = PostResource
    list_display = [
        "title",
        "slug",
        "author",
        "publish",
        "status",
        "custom_method",
        "image_preview",
    ]
    list_filter = ("status", "created", "publish", "author")
    search_fields = ("title", "body", "author__username")
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ["author"]
    date_hierarchy = "publish"
    ordering = ["status", "publish"]
    inlines = []
    list_display_links = ("title", "slug")
    readonly_fields = ("created", "updated", "image_preview")
    verbose_name = _("Пост")
    verbose_name_plural = _("Посты")
    formats = [CustomXLSXFormat]

    @admin.display(description=_("Пользовательский метод"))
    def custom_method(self, obj):
        return _("Пользовательское значение для {}").format(obj.title)

    @admin.display(description=_("Изображение"))
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px;" />', obj.image.url
            )
        return "-"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "print_post/<int:id>/",
                self.admin_site.admin_view(self.print_post),
                name="print_post",
            ),
        ]
        return custom_urls + urls

    def print_post(self, request, id):
        post = Post.objects.get(id=id)
        if post.image:
            post.image_url = request.build_absolute_uri(post.image.url)

        html = render_to_string("post_print.html", {"post": post})
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f"filename=post_{post.id}.pdf"
        css = CSS(
            string="""
            @page { size: A4; margin: 1cm; }
            img { max-width: 100%; height: auto; }
        """
        )
        HTML(string=html).write_pdf(response, stylesheets=[css])
        return response

    def print_post_action(self, request, queryset):
        if queryset.count() == 1:
            post = queryset.first()
            return self.print_post(request, post.id)
        else:
            self.message_user(
                request, _("Пожалуйста, выберите только одну публикацию для печати.")
            )

    print_post_action.short_description = _("Генерация PDF документа")
    actions = [print_post_action]


class ClientResource(resources.ModelResource):
    full_name = fields.Field(
        column_name="ФИО", readonly=True, attribute="get_full_name"
    )
    phone_number = fields.Field(column_name="Телефон", attribute="phone_number")
    email = fields.Field(column_name="Email", readonly=True)

    class Meta:
        model = Client
        fields = ("id", "full_name", "email", "phone_number")
        export_order = fields
        verbose_name_rus = "Клиенты"

    def dehydrate_full_name(self, client):
        return (
            f"{client.last_name} {client.first_name} {client.patronymic or ''}".strip()
        )

    def dehydrate_email(self, client):
        return client.email or "Не указан"

    def dehydrate_document_status(self, client):
        return "Прикреплен" if client.document else "Отсутствует"


@admin.register(Client)
class ClientAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name", 
        "patronymic",
        "phone_number",
        "email",
        "document_link",
        #"has_user_account",
    )
    search_fields = ["first_name", "last_name", "patronymic", "phone_number", "email"]
    list_filter = ("last_name", "first_name")
    raw_id_fields = ["user"]
    list_per_page = 50
    resource_class = ClientResource
    formats = [CustomXLSXFormat]

    def document_status(self, obj):
        return "✓" if obj.document else "✗"

    document_status.short_description = "Документ"

    @admin.display(description="Документ")
    def document_link(self, obj):
        if obj.document:
            return format_html('<a href="{}">📄</a>', obj.document.url)
        return "—"


# Убедимся, что XLSX формат доступен
try:
    from import_export.formats.base_formats import XLSX

    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False


class CustomXLSXFormat(XLSX):
    def get_content_type(self):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet; charset=utf-8-sig"


class HouseResource(resources.ModelResource):
    name = fields.Field(column_name="Название", attribute="name")
    price = fields.Field(column_name="Цена за ночь (руб)")
    capacity = fields.Field(column_name="Вместимость", attribute="capacity")
    location = fields.Field(column_name="Местоположение")
    address_specified = fields.Field(column_name="Адрес указан")
    manager = fields.Field(column_name="Менеджер")

    class Meta:
        model = House
        fields = (
            "name",
            "price",
            "capacity",
            "location",
            "address_specified",
            "manager",
        )
        export_order = (
            "name",
            "price",
            "capacity",
            "location",
            "address_specified",
            "manager",
        )
        skip_unchanged = True
        report_skipped = False
        encoding = "utf-8-sig"

    def dehydrate_price(self, house):
        return f"{house.price_per_night} ₽"

    def dehydrate_address_specified(self, house):
        return "Да" if house.location else "Нет"

    def dehydrate_manager(self, house):
        if house.employee_id:
            return f"{house.employee_id.last_name} {house.employee_id.first_name}"
        return "Не назначен"

    def dehydrate_location(self, house):
        if house.location:
            return f"Свердловская область, {house.location.split(',')[-1].strip()}"
        return ""

    def before_export(self, queryset, *args, **kwargs):
        return queryset.select_related("employee_id")


class HouseImageInline(admin.TabularInline):
    model = HouseImage
    extra = 1
    fields = ('image', 'caption', 'order', 'is_main')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="75" style="object-fit: cover;" />', obj.image.url)
        return "Нет изображения"
    image_preview.short_description = 'Превью'


@admin.register(House)
class HouseAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "price_per_night",
        "capacity",
        "location_short",
        "get_address_specified",
        "get_manager",
        "status_badge",
        "image_preview",
    )
    list_filter = ("is_active", "employee_id", "price_per_night", "capacity")
    search_fields = ("name", "location", "description")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("employee_id",)
    ordering = ["name"]
    list_per_page = 30
    readonly_fields = ("image_preview",)
    resource_class = HouseResource
    formats = [CustomXLSXFormat]  # Используем кастомный XLSX
    verbose_name = _("Коттедж")
    verbose_name_plural = _("Коттеджи")
    list_editable = (
        "price_per_night",
        "capacity",
    )  # Добавляем возможность быстрого редактирования

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("name", "slug", "description", "is_active")},
        ),
        (
            "Характеристики",
            {"fields": ("location", "capacity", "price_per_night", "amenities")},
        ),
        (
            "Медиа",
            {
                "fields": ("image", "image_preview"),
                "classes": ("collapse"),
            },
        ),
    )

    def get_export_formats(self):
        if XLSX_AVAILABLE:
            return [CustomXLSXFormat]
        return super().get_export_formats()

    def get_address_specified(self, obj):
        return "Да" if obj.location else "Нет"

    get_address_specified.short_description = "Адрес указан"

    def get_manager(self, obj):
        if obj.employee_id:
            return f"{obj.employee_id.last_name} {obj.employee_id.first_name}"
        return "Не назначен"

    get_manager.short_description = "Менеджер"

    def get_export_filename(self, request, queryset, file_format):
        return f"houses_export_{timezone.now().strftime('%Y-%m-%d')}.xlsx"

    @admin.display(description="Цена")
    def price_display(self, obj):
        return f"{obj.price_per_night} ₽"

    @admin.display(description="Местоположение")
    def location_short(self, obj):
        return obj.location[:50] + "..." if len(obj.location) > 50 else obj.location

    @admin.display(description="Статус")
    def status_badge(self, obj):
        color = "green" if obj.is_active else "red"
        text = "Активен" if obj.is_active else "Неактивен"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, text
        )

    @admin.display(description="Изображение")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px;" />', obj.image.url
            )
        return "-"

    def image_display(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="200" style="object-fit: cover;" />', obj.image.url)
        return "Главное изображение не установлено"
    image_display.short_description = 'Текущее главное изображение'


@admin.register(HouseImage)
class HouseImageAdmin(admin.ModelAdmin):
    list_display = ('house', 'caption', 'order', 'is_main', 'image_preview')
    list_filter = ('house', 'is_main')
    list_editable = ('order', 'is_main')
    search_fields = ('house__name', 'caption')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="75" style="object-fit: cover;" />', obj.image.url)
        return "Нет изображения"
    image_preview.short_description = 'Превью'


class FacilityResource(resources.ModelResource):
    name = fields.Field(column_name="Название", attribute="name")
    house = fields.Field(column_name="Коттедж", attribute="house")
    location = fields.Field(column_name="Местоположение", attribute="location")
    status = fields.Field(column_name="Статус", attribute="status")

    class Meta:
        model = Facility
        fields = ("id", "name", "house", "location", "status")
        export_order = fields
        verbose_name_rus = "Удобства"


@admin.register(Facility)
class FacilityAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = FacilityResource
    formats = [CustomXLSXFormat]
    list_display = ("facility_id", "house_link", "name", "description", "status")
    search_fields = ("name", "description")
    list_display_links = ("name",)
    list_filter = ("status",)
    readonly_fields = ("facility_id",)
    raw_id_fields = ["house_id"]
    verbose_name = _("Удобство")
    verbose_name_plural = _("Удобства")

    @admin.display(description=_("Коттедж"))
    def house_link(self, obj):
        return format_html(
            '<a href="/admin/recreation/house/{}/change/">{}</a>',
            obj.house_id.house_id,
            obj.house_id.name,
        )


class ReviewResource(resources.ModelResource):
    client = fields.Field(column_name="Клиент", attribute="client")
    house = fields.Field(column_name="Коттедж", attribute="house")
    rating = fields.Field(column_name="Рейтинг", attribute="rating")
    created_at = fields.Field(column_name="Дата создания", attribute="created_at")

    class Meta:
        model = Review
        fields = ("id", "client", "house", "rating", "created_at")
        export_order = fields


@admin.register(Review)
class ReviewAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        "review_id",
        "client_link",
        "house_link",
        "rating",
        "short_comment",
        "created_at",
    )
    search_fields = ("client_id__last_name", "house_id__name", "comment")
    list_display_links = ("client_link", "house_link")
    list_filter = (
        "rating",
        ("created_at", DateFieldListFilter),
    )
    readonly_fields = ("review_id", "created_at")
    raw_id_fields = ["client_id", "house_id"]
    date_hierarchy = "created_at"
    resource_class = ReviewResource
    formats = [CustomXLSXFormat]

    @admin.display(description="Клиент")
    def client_link(self, obj):
        if obj.client_id:
            first_initial = (
                obj.client_id.first_name[0] if obj.client_id.first_name else ""
            )
            return f"{obj.client_id.last_name} {first_initial}."
        return "-"

    @admin.display(description="Коттедж")
    def house_link(self, obj):
        return obj.house_id.name if obj.house_id else "-"

    @admin.display(description="Комментарий")
    def short_comment(self, obj):
        if obj.comment:
            return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment
        return "-"


class EmployeeResource(resources.ModelResource):
    full_name = fields.Field(column_name="ФИО")
    position = fields.Field(column_name="Должность")
    contacts = fields.Field(column_name="Контакты")
    hire_date = fields.Field(column_name="Дата приема")

    class Meta:
        model = Employee
        fields = ("full_name", "position", "contacts", "hire_date")
        export_order = ("full_name", "position", "contacts", "hire_date")
        encoding = "utf-8-sig"

    def dehydrate_full_name(self, employee):
        return f"{employee.last_name} {employee.first_name} {employee.patronymic or ''}".strip()

    def dehydrate_position(self, employee):
        return str(employee.position_id) if employee.position_id else "Не указана"

    def dehydrate_contacts(self, employee):
        contact_parts = []
        if employee.phone:
            contact_parts.append(f"тел: {employee.phone}")
        if employee.email:
            contact_parts.append(f"email: {employee.email}")
        return ", ".join(contact_parts) or "Не указаны"

    def dehydrate_hire_date(self, employee):
        return (
            employee.hire_date.strftime("%d.%m.%Y")
            if employee.hire_date
            else "Не указана"
        )


@admin.register(Employee)
class EmployeeAdmin(BaseExportAdmin, admin.ModelAdmin):
    resource_class = EmployeeResource
    list_display = ("get_full_name", "get_position", "get_contacts", "get_hire_date")
    list_filter = ("position_id",)
    search_fields = ("last_name", "first_name", "phone", "email", "position_id__name")
    formats = [CustomXLSXFormat]
    raw_id_fields = ("position_id",)  # Добавляем для лучшего выбора должности
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Безопасное редактирование сотрудников"""
        from django.contrib import messages
        
        if object_id:
            obj = self.get_object(request, object_id)
            if obj and request.method == 'POST' and 'position_id' in request.POST:
                # Проверяем, что выбранная должность существует
                from .models import Position
                try:
                    position_id = request.POST.get('position_id')
                    if position_id and not Position.objects.filter(pk=position_id).exists():
                        messages.error(request, 'Выбранная должность не существует')
                        return super().changeform_view(request, object_id, form_url, extra_context)
                except (ValueError, Position.DoesNotExist):
                    messages.error(request, 'Некорректная должность')
                    return super().changeform_view(request, object_id, form_url, extra_context)
        
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Ограничиваем выбор только существующими должностями
        if db_field.name == "position_id":
            kwargs["queryset"] = Position.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_full_name(self, obj):
        return f"{obj.last_name} {obj.first_name} {obj.patronymic or ''}".strip()

    get_full_name.short_description = "ФИО"

    def get_position(self, obj):
        return str(obj.position_id) if obj.position_id else "-"

    get_position.short_description = "Должность"

    def get_contacts(self, obj):
        contacts = []
        if obj.phone:
            contacts.append(obj.phone)
        if obj.email:
            contacts.append(obj.email)
        return " | ".join(contacts) or obj.contact_info or "Не указаны"

    get_contacts.short_description = "Контакты"

    def get_hire_date(self, obj):
        return obj.hire_date.strftime("%d.%m.%Y") if obj.hire_date else "-"

    get_hire_date.short_description = "Дата приема"


class PositionResource(resources.ModelResource):
    name = fields.Field(column_name="Должность", attribute="name")
    responsibilities = fields.Field(
        column_name="Обязанности", attribute="responsibilities"
    )

    class Meta:
        model = Position
        fields = ("id", "name", "responsibilities")
        export_order = fields
        verbose_name_rus = "Должности"


@admin.register(Position)
class PositionAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = PositionResource
    formats = [CustomXLSXFormat]
    list_display = ("position_id", "name", "get_employee_count", "short_responsibilities")
    search_fields = ("name", "responsibilities")
    list_display_links = ("name",)
    list_filter = ("name",)
    readonly_fields = ("position_id", "get_employee_count_display")
    verbose_name = _("Должность")
    verbose_name_plural = _("Должности")
    
    # Запрещаем удаление должностей, на которые есть ссылки
    def has_delete_permission(self, request, obj=None):
        if obj:
            # Проверяем, есть ли сотрудники с этой должностью
            from .models import Employee
            if Employee.objects.filter(position_id=obj).exists():
                return False
        return super().has_delete_permission(request, obj)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Безопасное редактирование должностей"""
        from django.contrib import messages
        
        if object_id:
            # Для существующей должности проверяем ссылки
            obj = self.get_object(request, object_id)
            if obj and request.method == 'POST':
                # Проверяем, не пытаются ли изменить должность, на которую есть ссылки
                from .models import Employee
                if Employee.objects.filter(position_id=obj).exists():
                    old_name = obj.name
                    if 'name' in request.POST and request.POST['name'] != old_name:
                        messages.warning(
                            request, 
                            f'Нельзя изменить название должности "{old_name}", '
                            f'так как на нее ссылаются сотрудники. '
                            f'Сначала измените должности у сотрудников.'
                        )
                        # Восстанавливаем старое название
                        request.POST = request.POST.copy()
                        request.POST['name'] = old_name
        
        return super().changeform_view(request, object_id, form_url, extra_context)

    @admin.display(description="Кол-во сотрудников")
    def get_employee_count(self, obj):
        from .models import Employee
        return Employee.objects.filter(position_id=obj).count()

    @admin.display(description="Обязанности")
    def short_responsibilities(self, obj):
        # Убираем HTML теги для отображения в списке
        import re
        text = re.sub('<[^<]+?>', '', obj.responsibilities)
        return text[:100] + "..." if len(text) > 100 else text

    @admin.display(description="Количество сотрудников")
    def get_employee_count_display(self, obj):
        from .models import Employee
        count = Employee.objects.filter(position_id=obj).count()
        if count > 0:
            return f"{count} сотрудник(ов) - изменение ограничено"
        return "Нет сотрудников - можно редактировать"


class BookingServiceInline(admin.TabularInline):
    model = BookingService
    extra = 1
    raw_id_fields = ["service_id"]


class BookingResource(resources.ModelResource):
    client = fields.Field(column_name="Клиент", attribute="client")
    house = fields.Field(column_name="Коттедж", attribute="house")
    check_in_date = fields.Field(column_name="Дата заезда", attribute="check_in_date")
    check_out_date = fields.Field(column_name="Дата выезда", attribute="check_out_date")
    nights = fields.Field(column_name="Ночей", attribute="nights")
    total_cost = fields.Field(column_name="Общая стоимость", attribute="total_cost")

    class Meta:
        model = Booking
        fields = (
            "id",
            "client",
            "house",
            "check_in_date",
            "check_out_date",
            "nights",
            "total_cost",
        )
        export_order = fields
        verbose_name_rus = "Бронирования"


@admin.register(Booking)
class BookingAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        "booking_id",
        "get_client",
        "get_house", 
        "check_in_date",
        "check_out_date",
        "get_nights",
        "total_cost",
    )
    list_filter = ("house", "check_in_date", "check_out_date")
    date_hierarchy = "created_at"
    raw_id_fields = ("client_id", "house")
    list_select_related = True
    readonly_fields = ("get_nights_readonly", "booking_id", "created_at")
    resource_class = BookingResource
    formats = [CustomXLSXFormat]

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("client_id", "house", "client_name")},
        ),
        (
            "Даты бронирования",
            {"fields": ("check_in_date", "check_out_date", "guests")},
        ),
        (
            "Контактные данные", 
            {"fields": ("phone_number", "email"), "classes": ("collapse",)},
        ),
        ("Финансы", {"fields": ("base_cost", "total_cost")}),
        ("Дополнительные услуги", {"fields": ("services",)}),
        ("Дополнительно", {"fields": ("comment", "created_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Ночи")
    def get_nights_readonly(self, obj):
        return self.get_nights(obj)

    @admin.display(description="Клиент")
    def get_client(self, obj):
        if obj.client_id:
            return f"{obj.client_id.last_name} {obj.client_id.first_name[0]}."
        return obj.client_name or "-"

    @admin.display(description="Ночи")
    def get_nights(self, obj):
        if obj.check_in_date and obj.check_out_date:
            return (obj.check_out_date - obj.check_in_date).days
        return "-"

    @admin.display(description="Коттедж")
    def get_house(self, obj):
        if obj.house:
            return format_html(
                '<a href="/admin/recreation/house/{}/change/">{}</a>',
                obj.house.house_id,
                obj.house.name,
            )
        return "-"


# class EventResource(resources.ModelResource):
#     name = fields.Field(column_name="Название", attribute="name")
#     date = fields.Field(column_name="Дата", attribute="date")
#     location = fields.Field(column_name="Место проведения", attribute="location")

#     class Meta:
#         model = Event
#         fields = ("id", "name", "date", "location")
#         export_order = fields
#         verbose_name_rus = "Мероприятия"


# @admin.register(Event)
# class EventAdmin(admin.ModelAdmin):  # Убрали ExportMixin временно
#     list_display = ("name", "date", "location")
#     search_fields = ("name", "location")
#     list_filter = ("date",)
#     readonly_fields = ("event_id",)
    
#     # ВРЕМЕННО полность уберите все кастомные методы
    
#     fieldsets = (
#         ('Основная информация', {
#             'fields': ('name', 'date', 'location', 'event_url', 'image')
#         }),
#         ('Бронирование (необязательно)', {
#             'fields': ('booking_id',),
#             'classes': ('collapse',)
#         }),
#     )

#     def get_form(self, request, obj=None, **kwargs):
#         form = super().get_form(request, obj, **kwargs)
#         form.base_fields['booking_id'].required = False
#         form.base_fields['booking_id'].empty_label = "--- Не выбрано ---"
#         return form


class ServiceResource(resources.ModelResource):
    type = fields.Field(column_name="Тип услуги", attribute="type")
    name = fields.Field(column_name="Название", attribute="name")
    price = fields.Field(column_name="Цена", attribute="price")
    is_active = fields.Field(column_name="Активна", attribute="is_active")

    class Meta:
        model = Service
        fields = ("id", "name", "type", "price", "is_active")
        export_order = fields
        verbose_name_rus = "Услуги"


@admin.register(Service)
class ServiceAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = ServiceResource
    formats = [CustomXLSXFormat]
    list_display = (
        "service_id",
        "name",
        "short_description",
        "price",
        "quantity",
        "image_preview",
    )
    search_fields = ("name", "description")
    list_display_links = ("name",)
    list_filter = ("price",)
    readonly_fields = ("service_id", "image_preview")
    verbose_name = _("Услуга")
    verbose_name_plural = _("Услуги")

    @admin.display(description=_("Описание"))
    def short_description(self, obj):
        return (
            obj.description[:50] + "..."
            if len(obj.description) > 50
            else obj.description
        )

    @admin.display(description=_("Изображение"))
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px;" />', obj.image.url
            )
        return "-"


@admin.register(BookingService)
class BookingServiceAdmin(ExportMixin, admin.ModelAdmin):
    list_display = ("id", "service_link", "booking_link", "booking_date", "return_date")
    search_fields = ("service_id__name", "booking_id__booking_id")
    list_display_links = ("service_link", "booking_link")
    list_filter = ("booking_date", "return_date")
    raw_id_fields = ("service_id", "booking_id")  # Используем _id суффикс
    verbose_name = "Бронирование услуги"
    verbose_name_plural = "Бронирования услуг"

    @admin.display(description="Услуга")
    def service_link(self, obj):
        if obj.service_id:  # Используем service_id вместо service
            return format_html(
                '<a href="/admin/recreation/service/{}/change/">{}</a>',
                obj.service_id.service_id,
                obj.service_id.name,
            )
        return "-"

    @admin.display(description="Бронирование")
    def booking_link(self, obj):
        if obj.booking_id:  # Используем booking_id вместо booking
            return format_html(
                '<a href="/admin/recreation/booking/{}/change/">{}</a>',
                obj.booking_id.booking_id,
                f"Бронирование #{obj.booking_id.booking_id}",
            )
        return "-"


class PaymentResource(resources.ModelResource):
    booking_id = fields.Field(column_name="ID бронирования", attribute="booking")
    amount = fields.Field(column_name="Сумма", attribute="amount")
    payment_type = fields.Field(column_name="Тип оплаты", attribute="payment_type")
    status = fields.Field(column_name="Статус", attribute="status")
    payment_date = fields.Field(column_name="Дата платежа", attribute="payment_date")

    class Meta:
        model = Payment
        fields = ("id", "booking_id", "amount", "payment_type", "status", "payment_date")
        export_order = fields
        verbose_name_rus = "Платежи"

    def dehydrate_booking_id(self, obj):
        return obj.booking.booking_id if obj.booking else "-"


@admin.register(Payment)
class PaymentAdmin(ExportMixin, admin.ModelAdmin):  # <- ВАЖНО: PaymentAdmin вместо Payment
    resource_class = PaymentResource
    formats = [CustomXLSXFormat]
    list_display = (
        "id",
        "booking_link",
        "amount",
        "payment_type",
        "status",
        "payment_date",
    )
    search_fields = ("booking__booking_id", "yookassa_payment_id")
    list_display_links = ("booking_link",)
    list_filter = ("payment_date", "payment_type", "status")
    readonly_fields = ("id", "payment_date", "captured_at", "yookassa_payment_id")
    raw_id_fields = ["booking"]
    verbose_name = _("Платеж")
    verbose_name_plural = _("Платежи")

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'id', 
                'booking', 
                'yookassa_payment_id',
                'amount',
                'payment_type',
                'status'
            )
        }),
        ('Даты', {
            'fields': (
                'payment_date',
                'captured_at'
            )
        }),
    )

    @admin.display(description="Бронирование")
    def booking_link(self, obj):
        if obj.booking:
            return format_html(
                '<a href="/admin/recreation/booking/{}/change/">{}</a>',
                obj.booking.booking_id,
                f"Бронирование #{obj.booking.booking_id}",
            )
        return "-"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
    

# Админ-панель для пакетного конструктора (добавить в конец файла)
class PackageServiceInline(admin.TabularInline):
    model = PackageService
    extra = 1
    raw_id_fields = ['service']


class PackageOptionInline(admin.TabularInline):
    model = PackageOption
    extra = 1


@admin.register(TravelPackage)
class TravelPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'package_type', 'base_house', 'duration_days', 'base_price', 'local_discount', 'is_active']
    list_filter = ['package_type', 'is_active', 'base_house']
    search_fields = ['name', 'description']
    inlines = [PackageOptionInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'package_type', 'description', 'base_house', 'image')
        }),
        ('Параметры', {
            'fields': ('duration_days', 'min_guests', 'max_guests', 'base_price')
        }),
        ('Для местных жителей', {
            'fields': ('local_discount', 'quick_booking', 'flexible_checkin')
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
    )


@admin.register(PackageOption)
class PackageOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'package', 'option_type', 'price', 'popular_local', 'is_active']
    list_filter = ['option_type', 'popular_local', 'is_active', 'package']
    search_fields = ['name', 'description']


@admin.register(CustomPackageBooking)
class CustomPackageBookingAdmin(admin.ModelAdmin):
    list_display = ['booking', 'travel_package', 'total_package_price']
    list_filter = ['travel_package']
    raw_id_fields = ['booking']
    readonly_fields = ['total_package_price']