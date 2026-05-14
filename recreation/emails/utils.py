import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

def send_html_email(subject, to_email, template_name, context):
    """Универсальная отправка HTML-писем"""
    html_message = render_to_string(f'emails/{template_name}', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        html_message=html_message,
        fail_silently=False,  # Пока отладка – False, потом можно вернуть True
    )

def send_booking_confirmation(booking):
    """Отправка подтверждения бронирования"""
    try:
        nights = (booking.check_out_date - booking.check_in_date).days
        context = {
            'booking': booking,
            'house': booking.house,
            'nights': nights,
            'services': booking.services.all(),
        }
        send_html_email(
            subject=f'Подтверждение бронирования №{booking.booking_id} - База отдыха "Ёлки"',
            to_email=booking.email,
            template_name='booking_confirmation.html',
            context=context
        )
        logger.info(f"Booking confirmation email sent to {booking.email}")
    except Exception as e:
        logger.error(f"Failed to send booking confirmation: {str(e)}")

def send_payment_confirmation(payment):
    """Отправка подтверждения оплаты"""
    try:
        booking = payment.booking
        nights = (booking.check_out_date - booking.check_in_date).days
        context = {
            'payment': payment,
            'booking': booking,
            'house': booking.house,
            'nights': nights,
        }
        send_html_email(
            subject=f'Оплата подтверждена - Бронирование №{booking.booking_id}',
            to_email=booking.email,
            template_name='payment_confirmation.html',
            context=context
        )
        logger.info(f"Payment confirmation email sent for booking {booking.booking_id}")
    except Exception as e:
        logger.error(f"Failed to send payment confirmation: {str(e)}")