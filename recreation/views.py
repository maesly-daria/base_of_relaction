import logging, os, uuid, json
from datetime import datetime, timedelta
from django import forms
from django.urls import reverse 
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required, login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Case, When, IntegerField
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET
from django.views.generic import ListView
from .emails.utils import send_booking_confirmation, send_payment_confirmation
from rest_framework.response import Response
from rest_framework.views import APIView
from yookassa import Payment, Configuration
from yookassa.domain.common import SecurityHelper
from .utils.tinkoff_api import tinkoff_api

from .forms import (
    BookingForm,
    ClientForm,
    ClientRegistrationForm,
    CustomAuthenticationForm,
    CustomUserCreationForm,
    CustomUserChangeForm,
    AccountProfileForm,
    EmailPhoneAuthForm,
    HouseFilter,
    HouseForm,
    PostForm,
    UserProfileForm,
    PaymentMethodForm,
    LocalPackageBuilderForm,
    QuickBookingForm,
    PackageCustomizationForm,
)
from .models import Booking, Client, House, Post, Review, Service, Tag, Payment, TravelPackage, PackageOption, CustomPackageBooking

logger = logging.getLogger(__name__)

def get_rating_stats():
    """Функция для получения статистики рейтинга"""
    return Review.objects.aggregate(
        global_avg=Avg("rating"), 
        total=Count("review_id")
    )


# Главная страница
def home(request):
    rating_stats = get_rating_stats()
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
                    "image_url": house.get_image_url,
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
                "global_avg_rating": rating_stats["global_avg"] or 0,
                "global_total_reviews": rating_stats["total"],
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
    rating_stats = get_rating_stats()
    try:
        client = request.user.client
    except Client.DoesNotExist:
        client = Client.objects.create(
            user=request.user,
            last_name=request.user.last_name or "",
            first_name=request.user.first_name or "",
            patronymic=request.user.patronymic or "",
            email=request.user.email,
            phone_number=request.user.phone or "",
        )

    # ИСПРАВЛЕНИЕ: Получаем бронирования через Client, а не через User
    bookings = Booking.objects.filter(client_id=client).select_related("house")

    if request.method == "POST":
        form = AccountProfileForm(request.POST, request.FILES, instance=client, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлен")
            return redirect("account")
    else:
        form = AccountProfileForm(instance=client, user=request.user)
    
    return render(
        request,
        "account.html",
        {
            "form": form,
            "client": client,
            "bookings": bookings,
            "now": timezone.now().date(),
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        },
    )


def account(request):
    if not request.user.is_authenticated:
        return redirect("login")

    rating_stats = get_rating_stats()
    
    # Получаем бронирования с информацией о пакетах
    bookings = (
        Booking.objects.filter(client_id__user=request.user)
        .select_related("house", "client_id")
        .prefetch_related("services")
        .order_by('-check_in_date')
    )

    # Добавляем информацию о пакетах к каждому бронированию
    bookings_with_packages = []
    for booking in bookings:
        # Используем related_name 'custom_package' вместо прямого запроса
        booking.package_info = getattr(booking, 'custom_package', None)
        
        # Добавляем расчет количества ночей
        booking.nights = (booking.check_out_date - booking.check_in_date).days
        bookings_with_packages.append(booking)

    # Получаем или создаем профиль клиента
    try:
        client_profile = request.user.client
    except Client.DoesNotExist:
        # Создаем профиль клиента если не существует
        client_profile = Client.objects.create(
            user=request.user,
            last_name=request.user.last_name or "",
            first_name=request.user.first_name or "",
            patronymic=request.user.patronymic or "",
            email=request.user.email,
            phone_number=request.user.phone or "",
        )

    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        client_form = ClientForm(request.POST, request.FILES, instance=client_profile)

        if form.is_valid() and client_form.is_valid():
            form.save()
            client_form.save()
            messages.success(request, "Профиль успешно обновлен")
            return redirect("account")
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме")
    else:
        form = UserProfileForm(instance=request.user)
        client_form = ClientForm(instance=client_profile)

    context = {
        "form": form,
        "client_form": client_form,
        "client": client_profile,
        "bookings": bookings_with_packages,  # Используем обновленный список с пакетами
        "now": timezone.now().date(),
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    }

    return render(request, "account.html", context)


# Посты
def post_detail(request, id):
    """Детальная страница поста по ID"""
    post = get_object_or_404(Post, id=id)
    
    # Проверяем, что пост опубликован или пользователь имеет права
    if post.status != 'published' and not (request.user.is_staff or request.user.is_superuser or request.user == post.author):
        raise Http404("Post not found")
        
    context = {
        'post': post,
    }
    return render(request, 'blog/post_detail.html', context)

@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            # Обычные пользователи могут создавать только черновики
            if not (request.user.is_staff or request.user.is_superuser):
                post.status = 'draft'
            post.save()
            return redirect('post_detail', id=post.id)  # если используете ID
            # ИЛИ: return redirect('post_detail', slug=post.slug)  # если используете slug
    else:
        form = PostForm()
    return render(request, 'blog/post_form.html', {'form': form})

@login_required
def post_update(request, pk):
    rating_stats = get_rating_stats()
    post = get_object_or_404(Post, pk=pk)
    
    # Проверка прав: автор, staff или superuser
    if not (request.user == post.author or request.user.is_staff or request.user.is_superuser):
        return redirect('post_list')
    
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            # ИСПРАВЬТЕ РЕДИРЕКТ - используйте id
            return redirect("post_detail", id=post.id)
    else:
        form = PostForm(instance=post)
    
    return render(request, "blog/post_form.html", {
        "form": form,
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


def post_list(request):
    rating_stats = get_rating_stats()
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
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    }

    return render(request, "blog/post_list.html", context)


@login_required
def delete_old_posts(request):
    rating_stats = get_rating_stats()
    if request.method == "POST":
        old_posts = Post.objects.filter(
            publish__lt=timezone.now() - timedelta(days=365)
        )
        deleted_count = old_posts.delete()[0]
        messages.success(request, f"Удалено {deleted_count} старых постов")
        return redirect("post_list")
    return render(request, "blog/confirm_bulk_delete.html", {
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


# Коттеджи и бронирование
def cottages(request):
    rating_stats = get_rating_stats()
    check_in = request.GET.get("check_in", "")
    check_out = request.GET.get("check_out", "")
    guests = int(request.GET.get("guests", 2))

    # Базовая фильтрация только по гостям и активности
    houses = House.objects.filter(capacity__gte=guests, is_active=True)

    # Добавляем фильтрацию через django_filters
    house_filter = HouseFilter(request.GET, queryset=houses)
    filtered_houses = house_filter.qs

    # Подготовка данных для шаблона с проверкой доступности
    houses_data = []
    for house in filtered_houses:
        # Проверяем доступность для отображения в шаблоне
        is_available = True
        if check_in and check_out:
            try:
                check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
                check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()
                is_available = house.is_available(check_in_date, check_out_date)
            except ValueError:
                is_available = True
        
        houses_data.append({
            "obj": house,
            "image_url": house.get_image_url,
            "image_exists": house.image_exists(),
            "is_available": is_available,
        })
    
    return render(
        request,
        "cottages.html",
        {
            "houses_data": houses_data,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "guest_range": range(1, 21),
            "filter": house_filter,
            "today": timezone.now().date().isoformat(),
            "tomorrow": (timezone.now() + timedelta(days=1)).date().isoformat(),
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        },
    )


def cottage_detail(request, slug):
    rating_stats = get_rating_stats()
    cottage = get_object_or_404(House, slug=slug)
    reviews = Review.objects.filter(house_id=cottage).select_related('client_id__user')
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
    )

    # 2. Услуги, подходящие для этого коттеджа (по вместимости)
    recommended_services = Service.objects.filter(
        (Q(type="entertainment") | Q(type="relax"))
        & ~Q(price__lt=2000)
        & Q(quantity__gte=cottage.capacity * 0.5)
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

    amenities_list = []
    if cottage.amenities:
        amenities_list = cottage.amenities.split('\n')
    
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
    rating_stats = get_rating_stats()
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

    # Получаем доступные пакеты для этого дома и дат
    available_packages = []
    packages = TravelPackage.objects.filter(base_house=house, is_active=True)
    for package in packages:
        if package.is_available_for_dates(check_in_date, check_out_date):
            package.final_price = package.get_final_price(request.user)
            available_packages.append(package)

    # Обработка POST запроса
    if request.method == 'POST':
        print(f"DEBUG: Processing POST request with house: {house}")
        print(f"DEBUG: User: {request.user}, authenticated: {request.user.is_authenticated}")
        
        post_data = request.POST.copy()
        # Добавляем house в данные формы
        post_data['house'] = house.pk
        
        # Проверяем, выбран ли пакет
        selected_package_id = request.POST.get('selected_package')
        print(f"DEBUG: Selected package ID from form: {selected_package_id}")
        
        selected_package = None
        if selected_package_id:
            try:
                selected_package = TravelPackage.objects.get(
                    pk=selected_package_id, 
                    base_house=house,
                    is_active=True
                )
                print(f"DEBUG: Found package: {selected_package.name}")
            except TravelPackage.DoesNotExist:
                print(f"DEBUG: Package not found: {selected_package_id}")
                # Убедимся, что пакет доступен на выбранные даты
                if not selected_package.is_available_for_dates(check_in_date, check_out_date):
                    messages.error(request, "Выбранный пакет недоступен на указанные даты")
                    return redirect('booking') + f'?house={house_id}&check_in={check_in}&check_out={check_out}&guests={guests}'
                    
            except TravelPackage.DoesNotExist:
                messages.error(request, "Выбранный пакет не найден")
                return redirect('booking') + f'?house={house_id}&check_in={check_in}&check_out={check_out}&guests={guests}'
        
        # Если выбран пакет, создаем форму без проверки доступности дат
        if selected_package:
            form = BookingForm(post_data, disable_date_validation=True)
        else:
            form = BookingForm(post_data)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    booking = form.save(commit=False)
                    
                    # Связываем с клиентом
                    try:
                        client = Client.objects.get(user=request.user)
                    except Client.DoesNotExist:
                        client = Client.objects.create(
                            user=request.user,
                            last_name=request.user.last_name or "",
                            first_name=request.user.first_name or "",
                            patronymic=request.user.patronymic or "",
                            email=request.user.email,
                            phone_number=request.user.phone or "",
                        )
                    
                    booking.client_id = client
                    booking.save()
                    
                    if selected_package:
                        print(f"=== DEBUG BOOKING: Creating package booking ===")
                        print(f"Selected package: {selected_package.name} (ID: {selected_package.package_id})")
                        print(f"Selected package options: {selected_package.options.count()}")
                        
                        # Пакетное бронирование - добавляем услуги из пакета
                        package_options = selected_package.options.filter(is_active=True)
                        booking.services.set(package_options)
                        print(f"Services added to booking: {booking.services.count()}")
                        
                        # Создаем запись о пакетном бронировании
                        package_booking = CustomPackageBooking.objects.create(
                            booking=booking,
                            travel_package=selected_package,
                            total_package_price=selected_package.get_final_price(request.user),
                            custom_requests=post_data.get('custom_requests', '')
                        )
                        print(f"CustomPackageBooking created with ID: {package_booking.id}")
                        
                        # Добавляем выбранные опции пакета
                        selected_options_ids = request.POST.getlist('package_options')
                        if selected_options_ids:
                            selected_options = PackageOption.objects.filter(
                                id__in=selected_options_ids, 
                                package=selected_package
                            )
                            package_booking.selected_options.set(selected_options)
                            print(f"Selected options added: {selected_options.count()}")
                        
                        # Устанавливаем общую стоимость из пакета
                        booking.total_cost = package_booking.total_package_price
                        booking.save(update_fields=['total_cost'])
                        
                        print(f"Booking total cost set to: {booking.total_cost}")
                        print(f"=== DEBUG BOOKING: Package booking completed ===")
                        
                        messages.success(request, f"Пакет '{selected_package.name}' успешно забронирован!")
                        
                    else:
                        # Обычное бронирование
                        form.save_m2m()
                        booking.total_cost = booking.calculate_total_cost()
                        booking.save(update_fields=['total_cost'])
                        messages.success(request, "Бронирование успешно создано!")
                    
                    # ОТПРАВКА ПОДТВЕРЖДЕНИЯ БРОНИРОВАНИЯ
                    # send_booking_confirmation(booking)
                    transaction.on_commit(lambda: send_booking_confirmation(booking))
                    # ВРЕМЕННЫЙ ТЕСТ - после всех booking.save() и package_booking.save()
                    print(">>> ОТЛАДКА: перед вызовом send_booking_confirmation")
                    send_booking_confirmation(booking)
                    print(">>> ОТЛАДКА: после вызова send_booking_confirmation")
                    # messages.success(request, "Бронирование успешно создано! Проверьте вашу почту.")
                    return redirect('payment', booking_id=booking.booking_id)
                    
            except Exception as e:
                logger.error(f"Booking save error: {str(e)}", exc_info=True)
                messages.error(request, f"Ошибка при создании бронирования: {str(e)}")
                print(f"DEBUG: Booking creation error: {str(e)}")
        else:
            print(f"DEBUG: Form is invalid. Errors: {form.errors}")
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, "Пожалуйста, исправьте ошибки в форме")
    else:
        # GET запрос - пользователь уже авторизован
        initial_data = {
            'house': house.pk,
            'check_in_date': check_in_date,
            'check_out_date': check_out_date,
            'guests': guests_int,
            'client_name': request.user.get_full_name(),
            'email': request.user.email,
            'phone_number': getattr(request.user, 'phone', ''),
        }
            
        form = BookingForm(initial=initial_data)

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
            "available_packages": available_packages,
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        },
    )


@login_required
def payment(request, booking_id):
    rating_stats = get_rating_stats()
    
    try:
        booking = Booking.objects.select_related("house", "client_id").get(pk=booking_id)
        
        # Проверка прав доступа
        if booking.client_id.user != request.user:
            raise Http404("Бронирование не найдено")
            
    except Booking.DoesNotExist:
        raise Http404("Бронирование не найдено")

    nights = (booking.check_out_date - booking.check_in_date).days

    # Расчет сумм
    full_amount = float(booking.total_cost)
    prepayment_percent = getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)
    prepayment_amount = full_amount * prepayment_percent / 100
    remaining_amount = full_amount - prepayment_amount
    refund_days = getattr(settings, 'BOOKING_REFUND_DAYS', 3)

    if request.method == 'POST':
        form = PaymentMethodForm(request.POST)
        if form.is_valid():
            payment_method = form.cleaned_data['payment_method']
            
            # === ОПЛАТА ЧЕРЕЗ Т-БАНК ===
            if payment_method == 'tbank':
                try:
                    # Создаем уникальный ID заказа
                    # Формат: BOOKING_123_1612345678
                    order_id = f"BOOKING_{booking.booking_id}_{int(timezone.now().timestamp())}"
                    
                    # URL для возврата после оплаты
                    success_url = request.build_absolute_uri(
                        reverse('payment_success', kwargs={'payment_id': 0})
                    ).replace('/0/', f'/{booking.booking_id}/')
                    
                    fail_url = request.build_absolute_uri(
                        reverse('payment', kwargs={'booking_id': booking.booking_id})
                    )
                    
                    # Инициализируем платеж
                    success, payment_url, response = tinkoff_api.init_payment(
                        amount=full_amount,
                        order_id=order_id,
                        description=f"Оплата бронирования №{booking.booking_id} в базе отдыха Ёлки",
                        client_email=booking.email or request.user.email,
                        client_phone=booking.phone_number or request.user.phone,
                        client_name=booking.client_name or request.user.get_full_name(),
                        success_url=success_url,
                        fail_url=fail_url
                    )
                    
                    if success and payment_url:
                        # Сохраняем платеж в БД
                        payment_obj = Payment.objects.create(
                            booking=booking,
                            amount=full_amount,
                            payment_type='full',
                            status='pending',
                            yookassa_payment_id=response.get('PaymentId', f"tinkoff_{order_id}")
                        )
                        
                        logger.info(f"Payment created: {payment_obj.id}, redirecting to {payment_url}")
                        
                        # Перенаправляем на страницу оплаты Т-Банка
                        return redirect(payment_url)
                    else:
                        error_msg = response.get('Message', 'Неизвестная ошибка')
                        logger.error(f"Tinkoff payment failed: {error_msg}")
                        messages.error(request, f"Ошибка при создании платежа: {error_msg}")
                        
                except Exception as e:
                    logger.error(f"Tinkoff payment error: {e}")
                    messages.error(request, f"Ошибка: {str(e)}")
            
            # === ОСТАЛЬНЫЕ СПОСОБЫ ОПЛАТЫ ===
            elif payment_method == 'full':
                return create_yookassa_payment(request, booking, 'full')
            elif payment_method == 'prepayment':
                return create_yookassa_payment(request, booking, 'prepayment')
            elif payment_method == 'qr':
                messages.info(request, "Оплата по QR-коду будет доступна позже")
    else:
        form = PaymentMethodForm()

    return render(
        request,
        "payment.html",
        {
            "booking": booking,
            "house": booking.house,
            "nights": nights,
            "services": booking.services.all(),
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

def payment_instructions(request, payment_id):
    """Страница с инструкциями по ручной оплате"""
    payment = get_object_or_404(Payment, id=payment_id)
    booking = payment.booking
    
    context = {
        'payment': payment,
        'booking': booking,
        'phone_number': '+79026344757',
        'whatsapp_url': f'https://wa.me/79026344757?text=Подтверждаю%20оплату%20бронирования%20№{booking.booking_id}'
    }
    return render(request, 'payment_instructions.html', context)


def create_yookassa_payment(request, booking, payment_method):
    try:
        # Для тестового режима - сразу имитируем успешный платеж
        # # if settings.DEBUG:
        # #     # Определяем сумму
        #     if payment_method == 'full':
        #         amount = float(booking.total_cost)
        #         payment_type = 'full'
        #     else:
        #         prepayment_percent = getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)
        #         amount = float(booking.total_cost * prepayment_percent / 100)
        #         payment_type = 'prepayment'
            
        #     # Создаем запись платежа в базе (используем нашу модель Payment)
        #     payment_obj = Payment.objects.create(
        #         booking=booking,
        #         amount=amount,
        #         payment_type=payment_type,
        #         status='succeeded',
        #         yookassa_payment_id=f"test_{uuid.uuid4()}"
        #     )
        #     payment_obj.captured_at = timezone.now()
        #     payment_obj.save()
            
        #     # Обновляем статус бронирования
        #     booking.status = 'confirmed'
        #     booking.payment_status = 'paid' if payment_type == 'full' else 'partially_paid'
        #     booking.save()
            
        #     messages.success(request, f"Тестовый платеж на {amount:.0f} ₽ успешно создан!")
        #     return redirect('payment_success', payment_id=payment_obj.id)
        
        # Реальная интеграция с ЮKassa
        # else:
            # Импортируем здесь, чтобы избежать циклических импортов
            from yookassa import Configuration
            from yookassa import Payment as YooPayment
            
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

# def create_yookassa_payment(request, booking, payment_method):
#     try:
#         # Для тестового режима - сразу имитируем успешный платеж
#         if settings.DEBUG:
#             # Определяем сумму
#             if payment_method == 'full':
#                 amount = float(booking.total_cost)
#                 payment_type = 'full'
#             else:
#                 prepayment_percent = getattr(settings, 'BOOKING_PREPAYMENT_PERCENT', 30)
#                 amount = float(booking.total_cost * prepayment_percent / 100)
#                 payment_type = 'prepayment'
            
#             # Создаем запись платежа в базе (используем нашу модель Payment)
#             payment_obj = Payment.objects.create(
#                 booking=booking,
#                 amount=amount,
#                 payment_type=payment_type,
#                 status='succeeded',
#                 yookassa_payment_id=f"test_{uuid.uuid4()}"
#             )
#             payment_obj.captured_at = timezone.now()
#             payment_obj.save()
            
#             # Обновляем статус бронирования
#             booking.status = 'confirmed'
#             booking.payment_status = 'paid' if payment_type == 'full' else 'partially_paid'
#             booking.save()
            
#             messages.success(request, f"Тестовый платеж на {amount:.0f} ₽ успешно создан!")
#             return redirect('payment_success', payment_id=payment_obj.id)
        
#         # Реальная интеграция с ЮKassa (закомментирована)
#         # else:
#         #     from yookassa import Configuration
#         #     from yookassa import Payment as YooPayment
#         #     ... (весь код реальной интеграции)

#     except Exception as e:
#         logger.error(f"Payment creation error: {str(e)}")
#         import traceback
#         logger.error(f"Full traceback: {traceback.format_exc()}")
        
#         error_message = "Ошибка при создании платежа. Пожалуйста, попробуйте еще раз."
#         if "No module named 'yookassa'" in str(e):
#             error_message = "Система оплаты временно недоступна. Пожалуйста, попробуйте позже."
        
#         messages.error(request, error_message)
#         return redirect('payment', booking_id=booking.booking_id)


def payment_success(request, payment_id):
    rating_stats = get_rating_stats()
    try:
        payment = Payment.objects.get(id=payment_id)
        
        if payment.booking.client_id.user != request.user:
            raise Http404("Платеж не найден")
        
        if payment.status == 'succeeded':
            payment.booking.status = 'confirmed'
            payment.booking.payment_status = 'paid' if payment.payment_type == 'full' else 'partially_paid'
            payment.booking.save()
            
            # ОТПРАВКА ПОДТВЕРЖДЕНИЯ ОПЛАТЫ
            send_payment_confirmation(payment)
        
        messages.success(request, "Оплата прошла успешно! На вашу почту отправлено подтверждение.")
        
        return render(request, 'payment_success.html', {
            'payment': payment,
            'booking': payment.booking,
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
    rating_stats = get_rating_stats()
    if request.method == "POST":
        print("DEBUG: Form data:", request.POST)  # ДЛЯ ОТЛАДКИ
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            print("DEBUG: Form is valid, saving user...")
            user = form.save()
            print(f"DEBUG: User created - First: {user.first_name}, Last: {user.last_name}, Email: {user.email}")
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("account")
        else:
            print("DEBUG: Form errors:", form.errors)
            messages.error(request, "Пожалуйста, исправьте ошибки в форме")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/register.html", {
        "form": form,
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


@login_required
def all_reviews(request):
    rating_stats = get_rating_stats()
    
    # Получаем только забронированные пользователем коттеджи
    if request.user.is_authenticated:
        user_booked_houses = House.objects.filter(
            booking__client_id__user=request.user,  # Используем client_id вместо client
            booking__check_in_date__lte=timezone.now().date()
        ).distinct()
    else:
        user_booked_houses = House.objects.none()
    
    # Остальной код без изменений...
    user_filter = request.GET.get('user') == 'me'
    
    if user_filter and request.user.is_authenticated:
        reviews = Review.objects.filter(client_id__user=request.user)
    else:
        reviews = Review.objects.all()
    
    reviews = reviews.select_related('client_id', 'house_id').order_by('-created_at')
    
    paginator = Paginator(reviews, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_filter': user_filter,
        'houses': user_booked_houses,
        'global_avg_rating': rating_stats['global_avg'] or 0,
        'global_total_reviews': rating_stats['total'],
    }
    
    return render(request, 'all_reviews.html', context)


@login_required
def create_review(request):
    rating_stats = get_rating_stats()
    if request.method == "POST":
        try:
            house_id = request.POST.get("house_id")
            rating = request.POST.get("rating")
            comment = request.POST.get("comment")

            house = get_object_or_404(House, pk=house_id)
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
    rating_stats = get_rating_stats()
    review = get_object_or_404(Review, pk=pk)

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
    rating_stats = get_rating_stats()
    review = get_object_or_404(Review, pk=pk)

    if review.client_id.user != request.user:
        messages.error(request, "У вас нет прав для редактирования этого отзыва")
        return redirect("all_reviews")

    houses = House.objects.all()

    if request.method == "POST":
        try:
            house_id = request.POST.get("house_id")
            rating = request.POST.get("rating")
            comment = request.POST.get("comment")

            review.house_id = get_object_or_404(House, pk=house_id)
            review.rating = rating
            review.comment = comment
            review.save()

            messages.success(request, "Отзыв успешно обновлен!")
            return redirect("all_reviews")

        except Exception as e:
            messages.error(request, f"Ошибка при обновлении: {str(e)}")

    context = {
        "review": review,
        "houses": houses,
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
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
    rating_stats = get_rating_stats()
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("some_view_name")
    else:
        form = ClientRegistrationForm()

    return render(request, "create_client.html", {
        "form": form,
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


def login_view(request):
    rating_stats = get_rating_stats()
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("some-view-name")
        else:
            return render(request, "login.html", {
                "error": "Invalid credentials",
                "global_avg_rating": rating_stats["global_avg"] or 0,
                "global_total_reviews": rating_stats["total"],
            })
    return render(request, "login.html", {
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


@login_required
def post_delete(request, id):
    rating_stats = get_rating_stats()
    post = get_object_or_404(Post, id=id)
    if request.method == "POST":
        post.delete()
        return redirect("post_list")
    return render(request, "blog/post_confirm_delete.html", {
        "post": post,
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


def create_house(request):
    rating_stats = get_rating_stats()
    if request.method == "POST":
        form = HouseForm(request.POST, request.FILES)
        if form.is_valid():
            house = form.save()
            messages.success(request, "Дом успешно создан!")
            return redirect("house_detail", slug=house.slug)
    else:
        form = HouseForm()
    return render(request, "houses/create_house.html", {
        "form": form,
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


class CustomLoginView(auth_views.LoginView):
    form_class = CustomAuthenticationForm
    template_name = "registration/login.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rating_stats = get_rating_stats()
        context.update({
            "global_avg_rating": rating_stats["global_avg"] or 0,
            "global_total_reviews": rating_stats["total"],
        })
        return context


@login_required
def download_document(request, client_id):
    rating_stats = get_rating_stats()
    client = get_object_or_404(Client, pk=client_id)
    if client.user != request.user and not request.user.is_staff:
        raise PermissionDenied

    response = FileResponse(client.document.open(), as_attachment=True)
    return response


@login_required
def edit_post(request, post_id):
    rating_stats = get_rating_stats()
    post = get_object_or_404(Post, id=post_id)

    if not (request.user == post.author or request.user.is_superuser):
        raise PermissionDenied("У вас нет прав для редактирования этого поста")


class CottagesListView(ListView):
    model = House
    template_name = "recreation/house_list.html"
    context_object_name = "houses"

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = HouseFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rating_stats = get_rating_stats()
        context["filter"] = self.filterset
        context["global_avg_rating"] = rating_stats["global_avg"] or 0
        context["global_total_reviews"] = rating_stats["total"]
        return context


@login_required
def user_bookings(request):
    rating_stats = get_rating_stats()
    bookings = Booking.objects.filter(user=request.user).select_related("house")
    return render(request, "bookings/user_bookings.html", {
        "bookings": bookings,
        "global_avg_rating": rating_stats["global_avg"] or 0,
        "global_total_reviews": rating_stats["total"],
    })


@csrf_exempt
def yookassa_webhook(request):
    if request.method == 'POST':
        # if not SecurityHelper.is_ip_trusted(request.META['REMOTE_ADDR']):
        #     return JsonResponse({'status': 'invalid ip'}, status=400)
        
        event_json = json.loads(request.body)
        
        try:
            payment = Payment.objects.get(yookassa_payment_id=event_json['object']['id'])
            payment.status = event_json['object']['status']
            
            if event_json['object']['status'] == 'succeeded':
                payment.captured_at = timezone.now()
                
            payment.save()
            
        except Payment.DoesNotExist:
            pass
            
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'invalid method'}, status=400)


@login_required
@csrf_protect
def change_password(request):
    if request.method == 'POST':
        logger.info(f"Смена пароля для пользователя: {request.user.email}")
        
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            try:
                user = form.save()
                # КРИТИЧЕСКИ ВАЖНО: обновляем сессию
                update_session_auth_hash(request, user)
                
                logger.info(f"Пароль успешно изменен для: {request.user.email}")
                return JsonResponse({
                    'success': True,
                    'message': 'Пароль успешно изменен!'
                })
                
            except Exception as e:
                logger.error(f"Ошибка при сохранении пароля для {request.user.email}: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Ошибка сервера при сохранении пароля: {str(e)}'
                })
        else:
            # Детальный лог ошибок валидации
            errors = []
            for field, field_errors in form.errors.items():
                field_name = {
                    'old_password': 'Текущий пароль',
                    'new_password1': 'Новый пароль', 
                    'new_password2': 'Подтверждение пароля'
                }.get(field, field)
                
                for error in field_errors:
                    errors.append(f'{field_name}: {error}')
            
            error_message = ' '.join(errors)
            logger.warning(f"Ошибки валидации пароля для {request.user.email}: {error_message}")
            
            return JsonResponse({
                'success': False,
                'error': error_message
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Разрешены только POST-запросы'
    })

    
@login_required
def cancel_booking(request, booking_id):
    """Отмена бронирования - простая версия только с датами"""
    try:
        # Находим бронирование
        booking = get_object_or_404(
            Booking, 
            pk=booking_id,
            client_id__user=request.user
        )
        
        # Получаем текущую дату (без времени)
        today = timezone.now().date()
        
        # Рассчитываем дедлайн для отмены (1.5 дня = 36 часов)
        # Используем days=2 для надежности (48 часов)
        cancel_deadline_date = booking.check_in_date - timedelta(days=2)
        
        # Проверяем, можно ли отменить
        if today > cancel_deadline_date:
            days_over = (today - cancel_deadline_date).days
            messages.error(
                request, 
                f"Отмена возможна только не позднее, чем за 48 часов до забронированной даты. "
                f"Срок отмены истёк {days_over} дней назад."
            )
            return redirect('account')
        
        # Проверяем, что бронирование еще не началось
        if today >= booking.check_in_date:
            messages.error(request, "Нельзя отменить已经开始或已结束的预订")
            return redirect('account')
        
        # УДАЛЯЕМ бронирование
        booking_title = f"Бронирование #{booking.booking_id} для {booking.house.name}"
        booking.delete()
        
        messages.success(
            request, 
            f"{booking_title} успешно отменено."
        )
        
    except Booking.DoesNotExist:
        messages.error(request, "Бронирование не найдено или у вас нет прав для его отмены")
    except Exception as e:
        logger.error(f"Cancel booking error: {str(e)}", exc_info=True)
        messages.error(request, f"Произошла ошибка: {str(e)}")
    
    return redirect('account')


# Представления для пакетного конструктора (добавить в конец файла)
def package_builder(request):
    """Главная страница конструктора пакетов"""
    rating_stats = get_rating_stats()
    
    if request.method == 'POST':
        form = LocalPackageBuilderForm(request.POST)
        if form.is_valid():
            # Сохраняем параметры в сессии
            request.session['package_params'] = {
                'occasion': form.cleaned_data['occasion'],
                'guests': form.cleaned_data['guests'],
                'nights': form.cleaned_data['nights'],
            }
            return redirect('package_recommendations')
    else:
        form = LocalPackageBuilderForm()
    
    return render(request, 'packages/builder.html', {
        'form': form,
        'global_avg_rating': rating_stats["global_avg"] or 0,
        'global_total_reviews': rating_stats["total"],
    })


def package_recommendations(request):
    """Рекомендации пакетов на основе параметров"""
    rating_stats = get_rating_stats()
    params = request.session.get('package_params', {})
    
    if not params:
        return redirect('package_builder')
    
    # Подбор подходящих пакетов
    packages = TravelPackage.objects.filter(
        is_active=True,
        min_guests__lte=params.get('guests', 2),
        max_guests__gte=params.get('guests', 2),
    ).prefetch_related('options')
    
    # Проверяем, местный ли пользователь
    is_local = check_if_local(request.user)
    
    # Рассчитываем финальные цены
    for package in packages:
        package.final_price = package.calculate_price_for_locals() if is_local else package.base_price
        package.local_discount_amount = float(package.base_price) * float(package.local_discount) / 100 if is_local else 0
    
    return render(request, 'packages/recommendations.html', {
        'packages': packages,
        'params': params,
        'is_local': is_local,
        'global_avg_rating': rating_stats["global_avg"] or 0,
        'global_total_reviews': rating_stats["total"],
    })


def check_if_local(user):
    """Проверяем, является ли пользователь местным"""
    if not user.is_authenticated:
        return False
    
    # Проверяем по предыдущим бронированиям (если было 2+ брони - считаем местным)
    try:
        client = Client.objects.get(user=user)
        booking_count = Booking.objects.filter(client_id=client).count()
        return booking_count >= 2
    except (Client.DoesNotExist, AttributeError):
        return False


def package_customize(request, package_id):
    """Кастомизация выбранного пакета"""
    rating_stats = get_rating_stats()
    package = get_object_or_404(TravelPackage, pk=package_id)
    params = request.session.get('package_params', {})
    is_local = check_if_local(request.user)
    # Получаем параметры из GET-запроса или сессии
    house_id = request.GET.get('house')
    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')
    guests = request.GET.get('guests')

    if house_id and check_in and check_out and guests:
        # Сохраняем в сессии для использования при бронировании
        request.session['booking_params'] = {
            'house_id': house_id,
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests,
        }
    
    if request.method == 'POST':
        form = PackageCustomizationForm(request.POST, package=package)
        if form.is_valid():
            # Сохраняем кастомизацию в сессии
            request.session['customized_package'] = {
                'package_id': package_id,
                'selected_options': [opt.id for opt in form.cleaned_data['selected_options']],
                'custom_requests': form.cleaned_data['custom_requests'],
            }
            return redirect('package_booking')
    else:
        form = PackageCustomizationForm(package=package)
    
    # Расчет стоимости
    base_price = package.calculate_price_for_locals() if is_local else package.base_price
    options = package.options.filter(is_active=True)
    
    return render(request, 'packages/customize.html', {
        'package': package,
        'form': form,
        'params': params,
        'base_price': base_price,
        'options': options,
        'is_local': is_local,
        'global_avg_rating': rating_stats["global_avg"] or 0,
        'global_total_reviews': rating_stats["total"],
    })


@login_required
def package_booking(request):
    """Оформление бронирования пакета"""
    rating_stats = get_rating_stats()
    package_data = request.session.get('customized_package', {})
    params = request.session.get('package_params', {})
    
    if not package_data or not params:
        return redirect('package_builder')
    
    package = get_object_or_404(TravelPackage, pk=package_data['package_id'])
    selected_options = PackageOption.objects.filter(id__in=package_data.get('selected_options', []))
    is_local = check_if_local(request.user)
    
    # Расчет итоговой стоимости
    base_price = package.calculate_price_for_locals() if is_local else package.base_price
    options_price = sum(float(opt.price) for opt in selected_options)
    total_price = base_price + options_price
    
    if request.method == 'POST':
        # Создаем обычное бронирование коттеджа
        booking_form = BookingForm(request.POST)
        if booking_form.is_valid():
            try:
                with transaction.atomic():
                    # Создаем основное бронирование
                    booking = booking_form.save(commit=False)
                    
                    # Связываем с клиентом
                    try:
                        client = Client.objects.get(user=request.user)
                    except Client.DoesNotExist:
                        client = Client.objects.create(
                            user=request.user,
                            last_name=request.user.last_name or "",
                            first_name=request.user.first_name or "",
                            patronymic=request.user.patronymic or "",
                            email=request.user.email,
                            phone_number=request.user.phone or "",
                        )
                    
                    booking.client_id = client
                    booking.house = package.base_house
                    booking.total_cost = total_price
                    booking.save()
                    
                    # Создаем запись о пакетном бронировании
                    package_booking = CustomPackageBooking.objects.create(
                        booking=booking,
                        travel_package=package,
                        total_package_price=total_price,
                        custom_requests=package_data.get('custom_requests', '')
                    )
                    package_booking.selected_options.set(selected_options)
                    
                    # Очищаем сессию
                    request.session.pop('package_params', None)
                    request.session.pop('customized_package', None)
                    
                    messages.success(request, "Пакетный тур успешно забронирован!")
                    return redirect('payment', booking_id=booking.booking_id)
                    
            except Exception as e:
                logger.error(f"Package booking error: {str(e)}")
                messages.error(request, f"Ошибка при бронировании: {str(e)}")
    else:
        # Предзаполняем форму бронирования
        check_in_date = datetime.now().date() + timedelta(days=7)
        check_out_date = check_in_date + timedelta(days=int(params.get('nights', 2)))
        
        initial_data = {
            'house': package.base_house.pk,
            'check_in_date': check_in_date,
            'check_out_date': check_out_date,
            'guests': params.get('guests', 2),
            'client_name': request.user.get_full_name(),
            'email': request.user.email,
            'phone_number': getattr(request.user, 'phone', ''),
        }
        booking_form = BookingForm(initial=initial_data)
        booking_form.fields['house'].widget = forms.HiddenInput()
    
    return render(request, 'packages/booking.html', {
        'package': package,
        'selected_options': selected_options,
        'total_price': total_price,
        'params': params,
        'booking_form': booking_form,
        'custom_requests': package_data.get('custom_requests', ''),
        'is_local': is_local,
        'global_avg_rating': rating_stats["global_avg"] or 0,
        'global_total_reviews': rating_stats["total"],
    })


@login_required
def quick_booking(request):
    """Быстрое бронирование для постоянных клиентов"""
    rating_stats = get_rating_stats()
    
    if request.method == 'POST':
        form = QuickBookingForm(request.POST)
        if form.is_valid():
            # Создаем быстрое бронирование
            house = form.cleaned_data['house']
            check_in = form.cleaned_data['check_in']
            nights = form.cleaned_data['nights']
            guests = form.cleaned_data['guests']
            
            check_out = check_in + timedelta(days=nights)
            
            # Автозаполнение данных пользователя
            try:
                client = Client.objects.get(user=request.user)
                
                booking = Booking.objects.create(
                    client_id=client,
                    house=house,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    guests=guests,
                    client_name=request.user.get_full_name(),
                    email=request.user.email,
                    phone_number=request.user.phone or '',
                    total_cost=house.price_per_night * nights
                )
                
                messages.success(request, f"Быстрое бронирование создано! Стоимость: {booking.total_cost} руб.")
                return redirect('payment', booking_id=booking.booking_id)
                
            except Exception as e:
                logger.error(f"Quick booking error: {str(e)}")
                messages.error(request, "Ошибка при создании бронирования")
    else:
        # Предлагаем последний забронированный коттедж
        last_house = None
        try:
            client = Client.objects.get(user=request.user)
            last_booking = Booking.objects.filter(client_id=client).last()
            if last_booking:
                last_house = last_booking.house
        except:
            pass
        
        initial = {'house': last_house} if last_house else {}
        form = QuickBookingForm(initial=initial)
    
    return render(request, 'packages/quick_booking.html', {
        'form': form,
        'global_avg_rating': rating_stats["global_avg"] or 0,
        'global_total_reviews': rating_stats["total"],
    })