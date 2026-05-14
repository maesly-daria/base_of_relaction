from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_booking_confirmation(booking):
    """Отправка подтверждения бронирования с использованием HTML-шаблона"""
    from ..models import House  # импорт внутри, чтобы избежать циклических ссылок
    house = booking.house
    nights = (booking.check_out_date - booking.check_in_date).days
    services = booking.services.all()
    
    context = {
        'booking': booking,
        'house': house,
        'nights': nights,
        'services': services,
    }
    send_html_email(
        subject=f'Бронирование #{booking.booking_id} на базе "Ёлки"',
        to_email=booking.email,
        template_name='booking_confirmation.html',
        context=context
    )

def send_payment_confirmation(payment):
    """Отправка подтверждения оплаты"""
    booking = payment.booking
    house = booking.house
    nights = (booking.check_out_date - booking.check_in_date).days
    context = {
        'payment': payment,
        'booking': booking,
        'house': house,
        'nights': nights,
    }
    send_html_email(
        subject=f'Оплата бронирования #{booking.booking_id} подтверждена',
        to_email=booking.email,
        template_name='payment_confirmation.html',
        context=context
    )