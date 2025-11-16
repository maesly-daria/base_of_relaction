from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .admin import PostAdmin
from .api import BookingViewSet, HouseHistoryViewSet, HouseViewSet, ReviewViewSet
from .models import Post
from .views import (
    CustomLoginView,
    account_view,
    create_review,
    delete_review,
    register_view,
)

router = DefaultRouter()
router.register(r"houses", HouseViewSet)
router.register(r"bookings", BookingViewSet)
router.register(r"reviews", ReviewViewSet)

urlpatterns = (
    [
        path("", views.home, name="home"),
        # path('login/', views.login_view, name='login'),
        path("posts/", views.post_list, name="post_list"),
        path("posts/<slug:slug>/", views.post_detail, name="post_detail"),
        path("posts/<int:id>/", views.post_detail, name="post_detail"),
        path("posts/<int:pk>/edit/", views.post_update, name="post_update"),
        path("posts/<int:pk>/delete/", views.post_delete, name="post_delete"),
        # path('clients/', views.client_list, name='client_list'),
        # path('houses/', views.house_list, name='house_list'),
        path("create_post/", views.post_create, name="create_post"),
        # path('create_house/', views.create_house, name='create_house'),
        path("reviews/", views.all_reviews, name="all_reviews"),
        path("cottages/", views.cottages, name="cottages"),
        path("booking/", views.booking, name="booking"),
        path("payment/<int:booking_id>/", views.payment, name="payment"),
        path("cottages/<slug:slug>/", views.cottage_detail, name="cottage_detail"),
        # path('cottages/<slug:slug>/modal/', cottage_modal_data, name='cottage_modal_data'),
        path("account/", account_view, name="account"),
        path("register/", register_view, name="register"),
        path("login/", CustomLoginView.as_view(), name="login"),
        path("logout/", LogoutView.as_view(), name="logout"),
        path(
            "api/houses/<int:pk>/",
            views.HouseDetailAPI.as_view(),
            name="house-api-detail",
        ),
        # path('services/<int:service_id>/modal/', views.service_modal_data, name='service_modal_data'),
        # path('services/<int:pk>/', views.service_detail, name='service_detail'),
        # path('services/<int:service_id>/', views.service_detail, name='service_detail'),
        path("api/services/<int:pk>/", views.service_data, name="service-detail"),
        path("services/<int:pk>/modal/", views.service_data, name="service-modal"),
        path("reviews/add/", create_review, name="review_add"),
        path("reviews/<int:pk>/edit/", views.update_review, name="review_edit"),
        path("reviews/<int:pk>/delete/", delete_review, name="review_delete"),
        path("reviews/", views.all_reviews, name="all_reviews"),
        path("my-bookings/", views.user_bookings, name="user_bookings"),
        path("api/", include(router.urls)),
        path(
            "api/houses/<int:house_id>/history/",
            HouseHistoryViewSet.as_view({"get": "list"}),
        ),
        path('payment/success/<int:payment_id>/', views.payment_success, name='payment_success'),
        path('payment/webhook/yookassa/', views.yookassa_webhook, name='yookassa_webhook'),
    ]
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin_instance = PostAdmin(Post, admin.site)
urlpatterns += [
    path("admin/print_post/<int:id>/", admin_instance.print_post, name="print_post"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
