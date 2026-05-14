from django.contrib.auth.backends import ModelBackend
from django.db.models import Q  # ДОБАВЬТЕ этот импорт
from .models import CustomUser

class EmailPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Используем Q для поиска по email или phone
            user = CustomUser.objects.get(
                Q(email=username) | Q(phone=username)
            )
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None
        except CustomUser.MultipleObjectsReturned:
            # Если найдено несколько пользователей, вернем None
            return None