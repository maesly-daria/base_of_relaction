from django import template
from django.conf import settings

register = template.Library()

@register.simple_tag
def get_min_password_length():
    for validator in settings.AUTH_PASSWORD_VALIDATORS:
        if validator['NAME'] == 'django.contrib.auth.password_validation.MinimumLengthValidator':
            return validator.get('OPTIONS', {}).get('min_length', 10)
    return 10