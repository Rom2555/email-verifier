"""
Интеграция с ЮKassa для приёма платежей.

Для работы нужно:
1. Зарегистрироваться на https://yookassa.ru
2. Получить shop_id и secret_key в личном кабинете
3. Добавить в settings.py:
   YOOKASSA_SHOP_ID = 'your_shop_id'
   YOOKASSA_SECRET_KEY = 'your_secret_key'
"""

from yookassa import Configuration, Payment as YooPayment
from yookassa.domain.notification import WebhookNotification
from django.conf import settings
import uuid


def configure_yookassa():
    """Настройка ЮKassa"""
    Configuration.account_id = getattr(settings, 'YOOKASSA_SHOP_ID', '')
    Configuration.secret_key = getattr(settings, 'YOOKASSA_SECRET_KEY', '')


def create_payment(amount, description, return_url, metadata=None):
    """
    Создание платежа в ЮKassa.
    
    Args:
        amount: Сумма в рублях (например, 490.00)
        description: Описание платежа
        return_url: URL для возврата после оплаты
        metadata: Дополнительные данные (например, {'user_id': 1, 'plan_id': 2})
    
    Returns:
        dict: {
            'id': 'payment_id',
            'confirmation_url': 'url_for_redirect',
            'status': 'pending'
        }
    """
    configure_yookassa()
    
    idempotence_key = str(uuid.uuid4())
    
    payment = YooPayment.create({
        "amount": {
            "value": str(amount),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url
        },
        "capture": True,  # Автоматическое подтверждение
        "description": description,
        "metadata": metadata or {}
    }, idempotence_key)
    
    return {
        'id': payment.id,
        'confirmation_url': payment.confirmation.confirmation_url,
        'status': payment.status
    }


def check_payment_status(payment_id):
    """
    Проверка статуса платежа.
    
    Args:
        payment_id: ID платежа в ЮKassa
    
    Returns:
        dict: {
            'status': 'succeeded' | 'pending' | 'canceled',
            'paid': True | False,
            'amount': '490.00',
            'metadata': {...}
        }
    """
    configure_yookassa()
    
    payment = YooPayment.find_one(payment_id)
    
    return {
        'status': payment.status,
        'paid': payment.paid,
        'amount': payment.amount.value,
        'metadata': payment.metadata
    }


def process_webhook(request_body):
    """
    Обработка webhook от ЮKassa.
    
    Args:
        request_body: Тело запроса (bytes или str)
    
    Returns:
        dict: {
            'event': 'payment.succeeded' | 'payment.canceled',
            'payment_id': '...',
            'metadata': {...}
        }
    """
    notification = WebhookNotification(request_body)
    
    return {
        'event': notification.event,
        'payment_id': notification.object.id,
        'status': notification.object.status,
        'metadata': notification.object.metadata
    }


# Пример использования в views.py:
"""
from money.yookassa_integration import create_payment, check_payment_status, process_webhook

# Создание платежа
@login_required
def subscribe(request, plan_name):
    plan = SubscriptionPlan.objects.get(name=plan_name)
    
    # Создаём платёж в ЮKassa
    payment_data = create_payment(
        amount=plan.price_monthly,
        description=f'Подписка {plan.display_name}',
        return_url=request.build_absolute_uri(reverse('money:payment_success')),
        metadata={
            'user_id': request.user.id,
            'plan_id': plan.id,
            'period': 'monthly'
        }
    )
    
    # Сохраняем в базу
    Payment.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price_monthly,
        payment_id=payment_data['id'],
        status='pending'
    )
    
    # Редирект на страницу оплаты ЮKassa
    return redirect(payment_data['confirmation_url'])


# Webhook для получения уведомлений
@csrf_exempt
def yookassa_webhook(request):
    if request.method == 'POST':
        data = process_webhook(request.body)
        
        if data['event'] == 'payment.succeeded':
            # Находим платёж
            payment = Payment.objects.get(payment_id=data['payment_id'])
            payment.status = 'completed'
            payment.completed_at = timezone.now()
            payment.save()
            
            # Активируем подписку
            profile = payment.user.profile
            profile.plan = payment.plan
            profile.subscription_start = timezone.now()
            profile.save()
        
        return JsonResponse({'status': 'ok'})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
"""
