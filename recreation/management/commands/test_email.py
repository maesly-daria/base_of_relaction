from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import smtplib
from email.mime.text import MIMEText

class Command(BaseCommand):
    help = 'Test email sending with detailed diagnostics'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email for testing')

    def handle(self, *args, **options):
        test_email = options.get('email') or 'dzvaaas@yandex.ru'
        
        self.stdout.write(f"🔧 Testing email configuration...")
        self.stdout.write(f"📧 From: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"📧 To: {test_email}")
        self.stdout.write(f"🔧 Backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"🔧 Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        self.stdout.write(f"🔧 TLS: {settings.EMAIL_USE_TLS}")
        
        try:
            # Тест 1: Простое письмо
            self.stdout.write("\n1️⃣ Testing simple email...")
            send_mail(
                'Тест email от базы отдыха "Ёлки"',
                'Это тестовое письмо для проверки работы email системы.\n\n'
                'Если вы получили это письмо, значит система работает корректно!',
                settings.DEFAULT_FROM_EMAIL,
                [test_email],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS('✅ Простое письмо отправлено!'))

            # Тест 2: HTML письмо
            self.stdout.write("\n2️⃣ Testing HTML email...")
            html_message = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; }
                    .header { background: #864421; color: white; padding: 20px; }
                    .content { padding: 20px; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🏕️ База отдыха "Ёлки"</h1>
                    <h2>Тестовое HTML письмо</h2>
                </div>
                <div class="content">
                    <p>Это <strong>HTML версия</strong> тестового письма.</p>
                    <p>Если вы видите оформление, значит HTML письма работают!</p>
                </div>
            </body>
            </html>
            """
            
            send_mail(
                'Тест HTML email - База отдыха "Ёлки"',
                'Это текстовая версия письма.',
                settings.DEFAULT_FROM_EMAIL,
                [test_email],
                html_message=html_message,
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS('✅ HTML письмо отправлено!'))

            self.stdout.write(self.style.SUCCESS('\n🎉 Все письма успешно отправлены!'))
            self.stdout.write('📨 Проверьте папку "Входящие" и "Спам" в вашей почте.')

        except smtplib.SMTPAuthenticationError as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка аутентификации: {e}'))
            self.stdout.write('🔑 Проверьте:')
            self.stdout.write('   - Правильность EMAIL_HOST_PASSWORD')
            self.stdout.write('   - Используется ли пароль приложения (не основной пароль)')
            self.stdout.write('   - Включена ли двухфакторная аутентификация')
            
        except smtplib.SMTPException as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка SMTP: {e}'))
            self.stdout.write('🔧 Проверьте:')
            self.stdout.write('   - Настройки EMAIL_HOST и EMAIL_PORT')
            self.stdout.write('   - Подключение к интернету')
            self.stdout.write('   - Блокировку антивирусом/файрволом')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Неожиданная ошибка: {e}'))