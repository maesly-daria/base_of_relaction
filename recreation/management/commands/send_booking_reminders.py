from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from recreation.emails.utils import send_html_email
from recreation.models import Booking

class Command(BaseCommand):
    help = 'Отправляет напоминания о предстоящем заезде за 1 день'

    def handle(self, *args, **options):
        tomorrow = timezone.now().date() + timedelta(days=1)
        bookings = Booking.objects.filter(
            check_in_date=tomorrow,
            status='confirmed'  # если есть поле статуса, или просто все
        )
        count = 0
        for booking in bookings:
            nights = (booking.check_out_date - booking.check_in_date).days
            context = {
                'booking': booking,
                'house': booking.house,
                'nights': nights,
                'services': booking.services.all(),
            }
            send_html_email(
                subject=f'Напоминание: заезд в "Ёлки" завтра!',
                to_email=booking.email,
                template_name='booking_reminder.html',  # потребуется создать
                context=context
            )
            count += 1
        self.stdout.write(f'Отправлено {count} напоминаний')