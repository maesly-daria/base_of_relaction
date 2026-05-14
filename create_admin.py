import os
import django
import sys

# Добавляем путь к проекту
sys.path.append('C:\\Projects\\base_relaction_django\\base_relaction')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base_relaction.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

try:
    # Пробуем создать суперпользователя
    user = User.objects.create_superuser(
        email='admin@example.com',
        password='admin12345',
        last_name='Adminov',
        first_name='Admin',
        patronymic='Adminovich',
        phone='+79999999999'
    )
    print("✅ Superuser created successfully!")
    print(f"Email: admin@example.com")
    print(f"Password: admin12345")
except Exception as e:
    print(f"❌ Error: {e}")
    print("Trying alternative method...")
    
    # Альтернативный способ
    try:
        user = User(
            email='admin@example.com',
            last_name='Adminov',
            first_name='Admin', 
            patronymic='Adminovich',
            phone='+79999999999',
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        user.set_password('admin12345')
        user.save()
        print("✅ Superuser created via alternative method!")
    except Exception as e2:
        print(f"❌ Alternative method also failed: {e2}")