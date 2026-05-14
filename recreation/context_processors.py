from django.conf import settings

def password_settings(request):
    min_password_length = 12
    for validator in settings.AUTH_PASSWORD_VALIDATORS:
        if validator['NAME'] == 'django.contrib.auth.password_validation.MinimumLengthValidator':
            min_password_length = validator.get('OPTIONS', {}).get('min_length', 12)
            break
    
    return {
        'MIN_PASSWORD_LENGTH': min_password_length,
    }