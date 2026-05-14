import os
import django
import sys

# Добавляем путь к проекту
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base_relaction.settings')
django.setup()

from recreation.models import Booking, House

def fix_null_bookings():
    print("=== Исправление NULL значений в таблице booking ===")
    
    # Найдем все бронирования с house_id = NULL
    null_bookings = Booking.objects.filter(house__isnull=True)
    null_count = null_bookings.count()
    
    print(f"Найдено {null_count} бронирований с house_id = NULL")
    
    if null_count == 0:
        print("✅ Нет записей для исправления!")
        return
    
    # Получим любой существующий дом для подстановки
    first_house = House.objects.first()
    
    if first_house:
        print(f"🏠 Используем дом: {first_house.name} (ID: {first_house.house_id})")
        
        # Обновим все NULL записи
        updated = null_bookings.update(house=first_house)
        print(f"✅ Обновлено {updated} записей")
        
        # Проверим результат
        remaining_null = Booking.objects.filter(house__isnull=True).count()
        print(f"📊 Осталось NULL записей: {remaining_null}")
    else:
        print("❌ Нет доступных домов! Создайте хотя бы один дом.")
        
        # Создаем тестовый дом если нет ни одного
        house = House.objects.create(
            name="Тестовый дом для миграции",
            location="Пермский край, п. Октябрьский", 
            capacity=2,
            price_per_night=2000,
            is_active=True
        )
        print(f"🏠 Создан тестовый дом: {house.name}")
        
        # Обновляем NULL записи
        updated = null_bookings.update(house=house)
        print(f"✅ Обновлено {updated} записей")

if __name__ == "__main__":
    fix_null_bookings()