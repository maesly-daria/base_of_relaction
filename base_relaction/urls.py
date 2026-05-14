import debug_toolbar
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from recreation.admin import PostAdmin
from recreation.models import Post  # Добавьте импорт модели Post

urlpatterns = [
    path("debug/", include(debug_toolbar.urls)),  # Добавлено для django-debug-toolbar
    path("admin/", admin.site.urls),
    path("", include("recreation.urls")),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# Добавляем маршрут для печати поста
admin_instance = PostAdmin(Post, admin.site)
urlpatterns.append(
    path("admin/print_post/<int:id>/", admin_instance.print_post, name="print_post")
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)