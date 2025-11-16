import logging, os, uuid, json
from datetime import datetime, timedelta
from django.urls import reverse 
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Case, When, IntegerField
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.generic import ListView
from rest_framework.response import Response
from rest_framework.views import APIView
from yookassa import Payment as YooPayment
from yookassa.domain.common import SecurityHelper

from .forms import (
    BookingForm,
    ClientForm,
    ClientRegistrationForm,
    CustomAuthenticationForm,
    CustomUserCreationForm,
    EmailPhoneAuthForm,
    HouseFilter,
    HouseForm,
    PostForm,
    UserProfileForm,
    PaymentMethodForm,
)
from .models import Booking, Client, House, Post, Review, Service, Tag, Payment

logger = logging.getLogger(__name__)


# Главная страница
def home(request):
    rating_stats = Review.objects.aggregate(
        global_avg=Avg("rating"), total=Count("review_id")
    )
    try:
        # 1. Получаем активные коттеджи с их рейтингами
        houses = House.objects.filter(is_active=True).order_by("name")
        cottages_data = []

        for house in houses:
            # Получаем средний рейтинг и количество отзывов для каждого коттеджа
            avg_rating = house.review_set.aggregate(Avg("rating"))["rating__avg"] or 0
            review_count = house.review_set.count()

            cottages_data.append(
                {
                    "obj": house,
                    "image_url": house.get_image_url,  # Используем свойство без вызова ()
                    "avg_rating": avg_rating,
                    "review_count": review_count,
                }
            )

        # 2. Получаем последние отзывы
        reviews = Review.objects.select_related("client_id", "house_id").order_by(
            "-created_at"
        )[2::6]

        # 3. Получаем последние посты
        latest_posts = Post.objects.filter(status="published").order_by("-publish")[:3]

        # 4. Получаем активные услуги
        services = Service.objects.filter(is_active=True).order_by("type", "name")[:6]

        return render(
            request,
            "home.html",
            {
                "cottages": cottages_data,
                "guest_range": range(1, 21),
                "reviews": reviews,
                "latest_posts": latest_posts,
                "services": services,
                "STATIC_URL": settings.STATIC_URL,
                "debug": settings.DEBUG,
                "global_avg_rating": rating_stats["global_avg"] or 0,
                "global_total_reviews": rating_stats["total"],
            },
        )

    except Exception as e:
        logger.error(f"Error in home view: {str(e)}")
        return render(
            request,
            "home.html",
            {
                "cottages": [],
                "guest_range": range(1, 21),
                "reviews": [],
                "latest_posts": [],
                "services": [],
                "debug": settings.DEBUG,
            },
        )


@require_GET
def service_data(request, pk):
    service = get_object_or_404(Service, pk=pk)

    # Получаем URL изображения
    if service.image and hasattr(service.image, "url"):
        image_url = service.image.url
    else:
        # Проверяем наличие изображения в static/images/
        image_name = f"service-{pk}.jpg"
        static_path = os.path.join("images", image_name)
        full_static_path = os.path.join(settings.STATIC_ROOT, static_path)

        if os.path.exists(full_static_path):
            image_url = os.path.join(settings.STATIC_URL, static_path)
        else:
            # Используем общее изображение "no-image.jpg" если специфичное не найдено
            image_url = os.path.join(settings.STATIC_URL, "images/no-image.jpg")

    response_data = {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "price": str(service.price),
        "type": service.get_type_display(),
        "image_url": image_url,
        "icon": service.get_icon(),
    }

    return JsonResponse(response_data)


# Личный кабинет
@login_required
def account_view(request):
    try:
        client = request.user.client_profile
    except Client.DoesNotExist:
        client = Client.objects.create(
            user=request.user,
            last_name=request.user.last_name or "",
            first_name=request.user.username or "",
            patronymic=request.user.patronymic or "",
            email=request.user.email,
            phone_number=request.user.phone or "",
        )

    # Получаем бронирования текущего пользователя
    bookings = Booking.objects.filter(user=request.user).select_related("house")

    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлен")
            return redirect("account")
    else:
        form = ClientForm(instance=client)

     # ДОБАВЬТЕ эти строки для отображения рейтинга в header
    rating_stats = Review.objects.aggregate(
        global_avg=Avg("rating"), 
        total=Count("review_id")
    )
    
    return render(
        request,
        "account.html",
        {
            "form": form,
            "client": client,
            "bookings": bookings,
            "now": timezone.now().date(),  # Для проверки активных бронирований
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        },
    )


def account(request):
    if not request.user.is_authenticated:
        return redirect("login")

    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related("house_id")
        .prefetch_related("services")
    )

    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        client_form = ClientForm(request.POST, instance=request.user.client_profile)

        if form.is_valid() and client_form.is_valid():
            form.save()
            client_form.save()
            messages.success(request, "Профиль успешно обновлен")
            return redirect("account")
    else:
        form = UserProfileForm(instance=request.user)
        client_form = ClientForm(instance=request.user.client_profile)

    # Добавляем текущую дату в контекст для отображения статуса бронирований
    context = {
        "form": form,
        "client_form": client_form,
        "bookings": bookings,
        "now": timezone.now().date(),
    }

    return render(request, "account.html", context)


# Посты
def post_detail(request, slug):
    post = get_object_or_404(Post, slug__iexact=slug)
    return render(request, "blog/post_detail.html", {"post": post})


@login_required
def post_create(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()  # Для сохранения тегов
            messages.success(request, "Пост успешно создан")
            return redirect("post_detail", id=post.id)
    else:
        form = PostForm()
    return render(request, "blog/post_form.html", {"form": form})


@login_required
def post_update(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == "POST":
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            return redirect("post_detail", slug=post.slug)
    else:
        form = PostForm(instance=post)
    return render(request, "blog/post_form.html", {"form": form})


def post_list(request):
    # Получаем все опубликованные посты с авторами и тегами
    posts = (
        Post.objects.filter(status="published")
        .select_related("author")
        .prefetch_related("tags")
    )

    # Получаем параметры фильтрации из GET-запроса
    search_query = request.GET.get("search", "")
    tag_query = request.GET.get("tag", "")
    order_by = request.GET.get("order_by", "-publish")

    # Применяем фильтры
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) | Q(body__icontains=search_query)
        )

    if tag_query:
        posts = posts.filter(tags__name=tag_query)

    # Применяем сортировку
    posts = posts.order_by(order_by).distinct()

    # Получаем все теги с количеством постов для фильтра
    all_tags = Tag.objects.annotate(num_posts=Count("posts")).filter(num_posts__gt=0)

    # Пагинация
    paginator = Paginator(posts, 5)
    page_number = request.GET.get("page")

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Подготавливаем контекст для шаблона
    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "tag_query": tag_query,
        "order_by": order_by,
        "all_tags": all_tags,
    }

    return render(request, "blog/post_list.html", context)


# def post_detail(request, slug):
#     post = get_object_or_404(Post, slug=slug)
#     return render(
#         request,
#         "blog/post_detail.html",
#         {
#             "post": post,
#             "user": request.user,  # Убедитесь, что user передается в контекст
#         },
#     )


@login_required
def delete_old_posts(request):
    if request.method == "POST":
        old_posts = Post.objects.filter(
            publish__lt=timezone.now() - timedelta(days=365)
        )
        deleted_count = old_posts.delete()[0]
        messages.success(request, f"Удалено {deleted_count} старых постов")
        return redirect("post_list")
    return render(request, "blog/confirm_bulk_delete.html")


# Коттеджи и бронирование
def cottages(request):
    # Текущая логика (даты и гости)
    check_in = request.GET.get("check_in", "")
    check_out = request.GET.get("check_out", "")
    guests = int(request.GET.get("guests", 2))

    # Фильтрация по гостям (сохраняем вашу проверку)
    houses = House.objects.filter(capacity__gte=guests)

    # Добавляем фильтрацию через django_filters (цена, название и т.д.)
    house_filter = HouseFilter(request.GET, queryset=houses)
    filtered_houses = house_filter.qs

    # Подготовка данных для шаблона (сохраняем ваш формат)
    houses_data = []
    for house in filtered_houses:
        houses_data.append(
            {
                "obj": house,
                "image_url": house.get_image_url,  # Убраны скобки, так как это свойство
                "image_exists": house.image_exists(),
            }
        )

    rating_stats = Review.objects.aggregate(
        global_avg=Avg("rating"), 
        total=Count("review_id")
    )
    
    return render(
        request,
        "cottages.html",
        {
            "houses_data": houses_data,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "guest_range": range(1, 21),
            "filter": house_filter,  # Передаём фильтр для формы
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        },
    )


def cottage_detail(request, slug):
    cottage = get_object_or_404(House, slug=slug)

    # 1. Похожие коттеджи (те же удобства или цена в том же диапазоне)
    similar_houses = (
        House.objects.filter(
            Q(
                price_per_night__range=(
                    cottage.price_per_night * 0.8,
                    cottage.price_per_night * 1.2,
                )
            ),
            is_active=True,
        )
        .exclude(pk=cottage.pk)
        .distinct()[:4]
    )  # Исключаем текущий и ограничиваем 4

    # 2. Услуги, подходящие для этого коттеджа (по вместимости)
    recommended_services = Service.objects.filter(
        (Q(type="entertainment") | Q(type="relax"))
        & ~Q(price__lt=2000)
        & Q(quantity__gte=cottage.capacity * 0.5)  # Услуги для компаний такого размера
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        data = {
            "name": cottage.name,
            "capacity": cottage.capacity,
            "price_per_night": cottage.price_per_night,
            "description": cottage.description,
            "amenities": cottage.amenities,
            "image_url": cottage.get_image_url(),
        }
        return JsonResponse(data)

    amenities_list = cottage.amenities.split("\n") if cottage.amenities else []

    rating_stats = Review.objects.aggregate(
        global_avg=Avg("rating"), 
        total=Count("review_id")
    )
    
    return render(
        request,
        "cottage_detail.html",
        {
            "cottage": cottage,
            "similar_houses": similar_houses,
            "recommended_services": recommended_services,
            "image_url": cottage.get_image_url,
            "image_exists": cottage.image_exists(),
            "amenities_list": amenities_list,
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        },
    )


def booking(request):
    # ПРОВЕРКА АУТЕНТИФИКАЦИИ - если не авторизован, перенаправляем на регистрацию
    if not request.user.is_authenticated:
        messages.warning(request, "Для бронирования необходимо войти в систему")
        return redirect(f"{reverse('login')}?next={request.get_full_path()}")

    house_id = request.GET.get("house")
    check_in = request.GET.get("check_in")
    check_out = request.GET.get("check_out")
    guests = request.GET.get("guests", 2)

    if not all([house_id, check_in, check_out, guests]):
        messages.error(request, "Необходимо указать все параметры бронирования")
        return redirect("cottages")

    try:
        house = House.objects.get(pk=house_id)
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()
        guests_int = int(guests)
        today = timezone.now().date()

        if check_in_date < today:
            messages.error(request, "Дата заезда не может быть в прошлом")
            return redirect("cottages")

        if check_out_date <= check_in_date:
            messages.error(request, "Дата выезда должна быть позже даты заезда")
            return redirect("cottages")

        nights = (check_out_date - check_in_date).days
        house_cost = house.price_per_night * nights

    except (House.DoesNotExist, ValueError) as e:
        messages.error(request, "Ошибка в данных бронирования")
        return redirect("cottages")

    # Обработка POST запроса
    if request.method == 'POST':
        print(f"DEBUG: Processing POST request with house: {house}")
        print(f"DEBUG: User: {request.user}, authenticated: {request.user.is_authenticated}")
        
        post_data = request.POST.copy()
        form = BookingForm(post_data, user=request.user, house=house)
        
        if form.is_valid():
            print("DEBUG: Form is valid, saving booking...")
            try:
                with transaction.atomic():
                    booking = form.save()
                    print(f"DEBUG: Booking saved successfully! ID: {booking.booking_id}")
                    messages.success(request, "Бронирование успешно создано!")
                    return redirect('payment', booking_id=booking.booking_id)
            except Exception as e:
                logger.error(f"Booking save error: {str(e)}", exc_info=True)
                messages.error(request, f"Ошибка при создании бронирования: {str(e)}")
        else:
            print(f"DEBUG: Form is invalid. Errors: {form.errors}")
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, "Пожалуйста, исправьте ошибки в форме")
    else:
        # GET запрос - пользователь уже авторизован
        initial_data = {
            'check_in_date': check_in_date,
            'check_out_date': check_out_date,
            'guests': guests_int,
            'client_name': request.user.get_full_name(),
            'email': request.user.email,
            'phone_number': getattr(request.user, 'phone', ''),
        }
            
        form = BookingForm(initial=initial_data, user=request.user, house=house)

    rating_stats = Review.objects.aggregate(
        global_avg=Avg("rating"), 
        total=Count("review_id")
    )

    return render(
        request,
        "booking.html",
        {
            "form": form,
            "house": house,
            "check_in": check_in_date,
            "check_out": check_out_date,
            "nights": nights,
            "guests": guests_int,
            "house_cost": house_cost,
            "services": Service.objects.filter(is_active=True),
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        },
    )


@login_required
def payment(request, booking_id):
    try:
        booking = Booking.objects.select_related("house", "client_id").get(
            pk=booking_id
        )
        nights = (booking.check_out_date - booking.check_in_date).days
        services = booking.services.all()

        # Проверка прав доступа
        if booking.user != request.user:
            raise Http404("Бронирование не найдено")

        rating_stats = Review.objects.aggregate(
            global_avg=Avg("rating"), 
            total=Count("review_id")
        )

        # Расчет сумм
        full_amount = booking.total_cost
        prepayment_amount = (booking.total_cost * getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)) / 100
        remaining_amount = full_amount - prepayment_amount
        prepayment_percent = getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)
        refund_days = getattr(settings, 'BOOKING_REFUND_DAYS', 3)

        if request.method == 'POST':
            form = PaymentMethodForm(request.POST)
            if form.is_valid():
                payment_method = form.cleaned_data['payment_method']
                
                # СОЗДАЕМ РЕАЛЬНЫЙ ПЛАТЕЖ В ЮKASSA
                return create_yookassa_payment(request, booking, payment_method)
                
        else:
            form = PaymentMethodForm()

        return render(
            request,
            "payment.html",
            {
                "booking": booking,
                "house": booking.house,
                "nights": nights,
                "services": services,
                "form": form,
                "full_amount": full_amount,
                "prepayment_amount": prepayment_amount,
                "remaining_amount": remaining_amount,
                "prepayment_percent": prepayment_percent,
                "refund_days": refund_days,
                "global_avg_rating": rating_stats["global_avg"] or 0,
                "global_total_reviews": rating_stats["total"],
            },
        )

    except Booking.DoesNotExist:
        raise Http404("Бронирование не найдено")


def create_yookassa_payment(request, booking, payment_method):
    try:
        # Для тестового режима - сразу имитируем успешный платеж
        if settings.DEBUG:
            # Определяем сумму
            if payment_method == 'full':
                amount = float(booking.total_cost)
                payment_type = 'full'
            else:
                prepayment_percent = getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)
                amount = float(booking.total_cost * prepayment_percent / 100)
                payment_type = 'prepayment'
            
            # Создаем запись платежа в базе (используем нашу модель Payment)
            payment_obj = Payment.objects.create(
                booking=booking,
                amount=amount,
                payment_type=payment_type,
                status='succeeded',
                yookassa_payment_id=f"test_{uuid.uuid4()}"
            )
            payment_obj.captured_at = timezone.now()
            payment_obj.save()
            
            messages.success(request, f"Тестовый платеж на {amount:.0f} ₽ успешно создан!")
            return redirect('payment_success', payment_id=payment_obj.id)
        
        # Реальная интеграция с ЮKassa
        else:
            # Импортируем здесь, чтобы избежать циклических импортов
            from yookassa import Configuration
            from yookassa import Payment as YooPayment  # Переименовываем чтобы избежать конфликта
            
            # Настраиваем ЮKassa
            Configuration.account_id = getattr(settings, 'YOOKASSA_SHOP_ID', 'test_shop_id')
            Configuration.secret_key = getattr(settings, 'YOOKASSA_SECRET_KEY', 'test_secret_key')
            
            # Определяем сумму
            if payment_method == 'full':
                amount = float(booking.total_cost)
                payment_type = 'full'
                description = f"Полная оплата бронирования {booking.house.name}"
            else:
                prepayment_percent = getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)
                amount = float(booking.total_cost * prepayment_percent / 100)
                payment_type = 'prepayment'
                description = f"Предоплата {prepayment_percent}% за {booking.house.name}"
            
            # Создаем запись платежа в базе (наша модель Payment)
            payment_obj = Payment.objects.create(
                booking=booking,
                amount=amount,
                payment_type=payment_type,
                status='pending'
            )
            
            # Создаем платеж в ЮKassa (YooPayment - это класс ЮKassa)
            idempotence_key = str(uuid.uuid4())
            
            yoo_payment = YooPayment.create({
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": request.build_absolute_uri(
                        reverse('payment_success', kwargs={'payment_id': payment_obj.id})
                    )
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "booking_id": booking.booking_id,
                    "payment_id": payment_obj.id,
                    "payment_type": payment_type
                }
            }, idempotence_key)
            
            # Сохраняем ID платежа ЮKassa
            payment_obj.yookassa_payment_id = yoo_payment.id
            payment_obj.save()
            
            # Перенаправляем на страницу оплаты ЮKassa
            return redirect(yoo_payment.confirmation.confirmation_url)
            
    except Exception as e:
        logger.error(f"Payment creation error: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Показываем информативное сообщение об ошибке
        error_message = "Ошибка при создании платежа. Пожалуйста, попробуйте еще раз."
        if "No module named 'yookassa'" in str(e):
            error_message = "Система оплаты временно недоступна. Пожалуйста, попробуйте позже."
        
        messages.error(request, error_message)
        return redirect('payment', booking_id=booking.booking_id)


def payment_success(request, payment_id):
    try:
        payment = Payment.objects.get(id=payment_id)
        
        # Проверяем, что платеж принадлежит текущему пользователю
        if payment.booking.user != request.user:
            raise Http404("Платеж не найден")
        
        # Обновляем статус бронирования
        booking = payment.booking
        # booking.booking_status = 'confirmed'  # Раскомментируйте когда добавите поле
        # booking.save()
        
        messages.success(request, "Оплата прошла успешно! Ваше бронирование подтверждено.")
        
        # Получаем статистику для header
        rating_stats = Review.objects.aggregate(
            global_avg=Avg("rating"), 
            total=Count("review_id")
        )
        
        return render(request, 'payment_success.html', {
            'payment': payment,
            'booking': booking,
            'global_avg_rating': rating_stats["global_avg"] or 0,
            'global_total_reviews': rating_stats["total"],
        })
        
    except Payment.DoesNotExist:
        raise Http404("Платеж не найден")


# Для входа
class LoginView(auth_views.LoginView):
    form_class = EmailPhoneAuthForm
    template_name = "registration/login.html"


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Явно указываем бэкенд при логине
            login(request, user, backend="recreation.backends.EmailPhoneBackend")
            return redirect("account")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/register.html", {"form": form})


def all_reviews(request):
    # Получаем список коттеджей для формы
    houses = House.objects.all()

    # Создаем базовый запрос
    reviews = Review.objects.all()

    # Добавляем аннотацию только для аутентифицированных пользователей
    if request.user.is_authenticated:
        reviews = reviews.annotate(
            is_mine=Case(
                When(client_id__user=request.user, then=1),
                default=0,
                output_field=IntegerField(),
            )
        ).order_by("-is_mine", "-created_at")
    else:
        reviews = reviews.order_by("-created_at")

    paginator = Paginator(reviews, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "houses": houses,  # Добавляем список домов в контекст
        "user": request.user,
    }
    return render(request, "all_reviews.html", context)


@login_required
def create_review(request):
    if request.method == "POST":
        try:
            house_id = request.POST.get("house_id")
            rating = request.POST.get("rating")
            comment = request.POST.get("comment")

            # Используем pk вместо id, так как Django автоматически создает первичный ключ
            house = get_object_or_404(House, pk=house_id)

            # Получаем или создаем клиента для текущего пользователя
            client, created = Client.objects.get_or_create(user=request.user)

            Review.objects.create(
                client_id=client, house_id=house, rating=rating, comment=comment
            )

            messages.success(request, "Ваш отзыв успешно добавлен!")
            return redirect("all_reviews")

        except Exception as e:
            messages.error(request, f"Ошибка при создании отзыва: {str(e)}")
            return redirect("all_reviews")

    return redirect("all_reviews")


@login_required
def delete_review(request, pk):
    review = get_object_or_404(Review, pk=pk)

    # Проверяем, что отзыв принадлежит текущему пользователю
    if review.client_id.user != request.user:
        messages.error(request, "Вы не можете удалить этот отзыв")
        return redirect("all_reviews")

    if request.method == "POST":
        review.delete()
        messages.success(request, "Отзыв успешно удален")
        return redirect("all_reviews")

    return redirect("all_reviews")


@login_required
def update_review(request, pk):
    review = get_object_or_404(Review, pk=pk)

    # Проверка прав доступа
    if review.client_id.user != request.user:
        messages.error(request, "У вас нет прав для редактирования этого отзыва")
        return redirect("all_reviews")

    houses = House.objects.all()

    if request.method == "POST":
        try:
            house_id = request.POST.get("house_id")
            rating = request.POST.get("rating")
            comment = request.POST.get("comment")

            # Обновляем данные отзыва
            review.house_id = get_object_or_404(House, pk=house_id)
            review.rating = rating
            review.comment = comment
            review.save()

            messages.success(request, "Отзыв успешно обновлен!")
            return redirect("all_reviews")

        except Exception as e:
            messages.error(request, f"Ошибка при обновлении: {str(e)}")

    # Передаем данные отзыва в контекст
    context = {
        "review": review,
        "houses": houses,
    }
    return render(request, "review_form.html", context)


class HouseDetailAPI(APIView):
    def get(self, request, pk):
        house = get_object_or_404(House, pk=pk)
        data = {
            "id": house.house_id,
            "name": house.name,
            "price_per_night": house.price_per_night,
            "capacity": house.capacity,
        }
        return Response(data)


def create_client(request):
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("some_view_name")
    else:
        form = ClientRegistrationForm()

    return render(request, "create_client.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect to a success page
            return redirect("some-view-name")
        else:
            # Return an error message
            return render(request, "login.html", {"error": "Invalid credentials"})
    return render(request, "login.html")


@login_required
def post_delete(request, id):
    post = get_object_or_404(Post, id=id)
    if request.method == "POST":
        post.delete()
        return redirect("post_list")
    return render(request, "blog/post_confirm_delete.html", {"post": post})


def create_house(request):
    if request.method == "POST":
        form = HouseForm(request.POST, request.FILES)
        if form.is_valid():
            house = form.save()
            messages.success(request, "Дом успешно создан!")
            return redirect(
                "house_detail", slug=house.slug
            )  # Или другой подходящий URL
    else:
        form = HouseForm()
    return render(request, "houses/create_house.html", {"form": form})


class CustomLoginView(auth_views.LoginView):
    form_class = CustomAuthenticationForm
    template_name = "registration/login.html"


@login_required
def download_document(request, client_id):
    client = get_object_or_404(Client, pk=client_id)
    if client.user != request.user and not request.user.is_staff:
        raise PermissionDenied

    response = FileResponse(client.document.open(), as_attachment=True)
    return response


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Проверка прав ТОЛЬКО здесь, внутри функции!
    if not (request.user == post.author or request.user.is_superuser):
        raise PermissionDenied("У вас нет прав для редактирования этого поста")


class CottagesListView(ListView):
    model = House
    template_name = "recreation/house_list.html"  # Главная страница с коттеджами
    context_object_name = "houses"

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = HouseFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs  # Возвращаем отфильтрованные данные

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset  # Передаём фильтр в шаблон
        return context


@login_required
def user_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related("house")
    return render(request, "bookings/user_bookings.html", {"bookings": bookings})

@csrf_exempt
def yookassa_webhook(request):
    if request.method == 'POST':
        # Проверяем подпись уведомления
        if not SecurityHelper().is_valid_ip(request.META['REMOTE_ADDR']):
            return JsonResponse({'status': 'invalid ip'}, status=400)
        
        event_json = json.loads(request.body)
        
        try:
            # Обрабатываем уведомление
            payment = Payment.objects.get(yookassa_payment_id=event_json['object']['id'])
            payment.status = event_json['object']['status']
            
            if event_json['object']['status'] == 'succeeded':
                payment.captured_at = timezone.now()
                
            payment.save()
            
        except Payment.DoesNotExist:
            pass
            
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'invalid method'}, status=400)