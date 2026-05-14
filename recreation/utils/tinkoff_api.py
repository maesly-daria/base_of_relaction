# recreation/utils/tinkoff_api.py
import hashlib
import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class TinkoffAPI:
    """
    Прямая интеграция с API Т-Банка
    Документация: https://www.tinkoff.ru/kassa/develop/api/
    """
    
    def __init__(self):
        # Тестовые данные (работают без регистрации!)
        self.terminal_key = 'TestTerminalKey'
        self.password = ''  # Для теста пароль не нужен
        self.api_url = 'https://rest-api-test.tinkoff.ru/v2/'  # Тестовый URL
        
        # Для продакшена нужно будет заменить на реальные данные
        # self.terminal_key = settings.TINKOFF_TERMINAL_KEY
        # self.password = settings.TINKOFF_PASSWORD
        # self.api_url = 'https://securepay.tinkoff.ru/v2/'
    
    def _generate_token(self, params: Dict[str, Any]) -> str:
        """
        Генерация токена для подписи запроса
        """
        # Убираем пустые значения и Token
        filtered = {}
        for k, v in params.items():
            if v not in (None, '', [], {}) and k != 'Token':
                filtered[k] = str(v)
        
        # Сортируем ключи по алфавиту
        sorted_keys = sorted(filtered.keys())
        
        # Формируем строку для подписи
        sign_string = ''
        for key in sorted_keys:
            sign_string += f"{key}={filtered[key]}"
        
        # Добавляем пароль (для теста он пустой)
        sign_string += self.password
        
        # Вычисляем SHA256 и переводим в верхний регистр
        token = hashlib.sha256(sign_string.encode('utf-8')).hexdigest().upper()
        
        logger.debug(f"Token string: {sign_string}")
        logger.debug(f"Generated token: {token}")
        
        return token
    
    def init_payment(self, 
                    amount: float,
                    order_id: str,
                    description: str = None,
                    client_email: str = None,
                    client_phone: str = None,
                    client_name: str = None,
                    success_url: str = None,
                    fail_url: str = None) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Инициализация платежа (метод Init)
        
        Args:
            amount: Сумма в рублях
            order_id: ID заказа в вашей системе
            description: Описание платежа
            client_email: Email клиента
            client_phone: Телефон клиента
            client_name: Имя клиента
            success_url: URL для возврата после успешной оплаты
            fail_url: URL для возврата после неуспешной оплаты
        
        Returns:
            (success, payment_url, response_data)
        """
        try:
            # Конвертируем рубли в копейки
            amount_kopecks = int(amount * 100)
            
            # Формируем данные для запроса
            data = {
                'TerminalKey': self.terminal_key,
                'Amount': amount_kopecks,
                'OrderId': order_id,
                'Description': description or f'Оплата заказа №{order_id}',
                'DATA': {}
            }
            
            # Добавляем данные клиента
            if client_email:
                data['DATA']['Email'] = client_email
            if client_phone:
                data['DATA']['Phone'] = client_phone
            if client_name:
                data['DATA']['Name'] = client_name
            
            # Добавляем URL для возврата
            if success_url:
                data['SuccessURL'] = success_url
            if fail_url:
                data['FailURL'] = fail_url
            
            # Генерируем токен
            data['Token'] = self._generate_token(data)
            
            logger.info(f"Sending Init request to Tinkoff: {data}")
            
            # Отправляем запрос
            response = requests.post(
                f"{self.api_url}Init",
                json=data,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Tinkoff response: {result}")
            
            if result.get('Success'):
                payment_url = result.get('PaymentURL')
                return True, payment_url, result
            else:
                error_msg = result.get('Message', 'Неизвестная ошибка')
                logger.error(f"Tinkoff error: {error_msg}")
                return False, None, result
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return False, None, {'Error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False, None, {'Error': str(e)}


# Создаем глобальный экземпляр
tinkoff_api = TinkoffAPI()