import re
import dns.resolver
import socket
import smtplib
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
import json

from .models import EmailVerification, UserProfile, SubscriptionPlan, APIKey, Payment


# Список одноразовых email доменов
DISPOSABLE_DOMAINS = {
    'tempmail.com', 'throwaway.email', 'guerrillamail.com', 'mailinator.com',
    '10minutemail.com', 'temp-mail.org', 'fakeinbox.com', 'trashmail.com',
    'yopmail.com', 'getnada.com', 'maildrop.cc', 'dispostable.com',
    'tempail.com', 'mohmal.com', 'emailondeck.com', 'tempr.email',
}

# Лимит для анонимных пользователей
ANONYMOUS_DAILY_LIMIT = 3


def get_client_ip(request):
    """Получить IP адрес клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def validate_email_syntax(email):
    """Проверка синтаксиса email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def get_domain(email):
    """Извлечь домен из email"""
    return email.split('@')[1] if '@' in email else ''


def check_mx_records(domain):
    """Проверка MX-записей домена"""
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        return True, [str(mx.exchange) for mx in mx_records]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, Exception):
        return False, []


def check_smtp_deliverable(email, mx_host):
    """Проверка доставляемости через SMTP"""
    try:
        server = smtplib.SMTP(timeout=10)
        server.connect(mx_host)
        server.helo('verify.local')
        server.mail('verify@verify.local')
        code, message = server.rcpt(email)
        server.quit()
        
        # 250 = адрес принят
        # 550, 551, 552, 553 = адрес не существует
        # 450, 451, 452 = временная ошибка
        if code == 250:
            return True
        elif code in [550, 551, 552, 553]:
            return False
        else:
            return None  # Неизвестно
    except smtplib.SMTPServerDisconnected:
        return None  # Сервер отключился - неизвестно
    except smtplib.SMTPConnectError:
        return None
    except Exception:
        return None


def is_disposable_email(domain):
    """Проверка на одноразовый email"""
    return domain.lower() in DISPOSABLE_DOMAINS


def verify_email(email):
    """Полная верификация email"""
    result = {
        'email': email,
        'is_valid_syntax': False,
        'has_mx_record': False,
        'is_deliverable': False,
        'is_deliverable_unknown': False,  # Новое поле
        'is_disposable': False,
        'domain': '',
        'mx_records': [],
        'error_message': '',
        'score': 0,
        'status': 'invalid',  # invalid, risky, unknown, valid
    }
    
    if not validate_email_syntax(email):
        result['error_message'] = 'Неверный формат email'
        result['status'] = 'invalid'
        return result
    
    result['is_valid_syntax'] = True
    domain = get_domain(email)
    result['domain'] = domain
    result['is_disposable'] = is_disposable_email(domain)
    
    has_mx, mx_records = check_mx_records(domain)
    result['has_mx_record'] = has_mx
    result['mx_records'] = mx_records
    
    if not has_mx:
        result['error_message'] = 'Домен не имеет MX-записей - почта не будет доставлена'
        result['status'] = 'invalid'
        return result
    
    # SMTP проверка
    if mx_records:
        mx_host = mx_records[0].rstrip('.')
        deliverable = check_smtp_deliverable(email, mx_host)
        
        if deliverable is True:
            result['is_deliverable'] = True
            result['status'] = 'valid'
        elif deliverable is False:
            result['is_deliverable'] = False
            result['error_message'] = 'Почтовый ящик не существует на сервере'
            result['status'] = 'invalid'
        else:
            # Неизвестно - сервер не дал точного ответа
            result['is_deliverable_unknown'] = True
            result['error_message'] = 'Не удалось проверить существование ящика (сервер не отвечает или блокирует проверку)'
            result['status'] = 'unknown'
    
    # Проверка на одноразовый email
    if result['is_disposable']:
        result['status'] = 'risky'
        result['error_message'] = 'Одноразовый email - может быть удалён в любой момент'
    
    # Расчёт баллов с учётом неопределённости
    score = 0
    if result['is_valid_syntax']:
        score += 25
    if result['has_mx_record']:
        score += 25
    
    if result['is_deliverable']:
        score += 40
    elif result['is_deliverable_unknown']:
        score += 20  # Только половина баллов если неизвестно
    # Если is_deliverable = False, баллы не добавляем
    
    if not result['is_disposable']:
        score += 10
    
    result['score'] = score
    
    return result


def check_anonymous_limit(request):
    """Проверка лимита для анонимных пользователей"""
    ip = get_client_ip(request)
    today = date.today()
    count = EmailVerification.objects.filter(
        ip_address=ip,
        user__isnull=True,
        created_at__date=today
    ).count()
    return count < ANONYMOUS_DAILY_LIMIT, ANONYMOUS_DAILY_LIMIT - count


def home(request):
    """Главная страница с формой верификации"""
    context = {
        'remaining_checks': ANONYMOUS_DAILY_LIMIT,
        'is_authenticated': request.user.is_authenticated,
    }
    
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.plan:
            context['remaining_checks'] = profile.plan.daily_limit - profile.daily_verifications
            context['plan'] = profile.plan
    else:
        can_verify, remaining = check_anonymous_limit(request)
        context['remaining_checks'] = remaining
    
    return render(request, 'home/index.html', context)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='30/m', method='POST', block=True)  # 30 запросов в минуту с IP
def verify_email_api(request):
    """API endpoint для верификации email"""
    # Проверка API ключа
    api_key_header = request.headers.get('X-API-Key') or request.GET.get('api_key')
    api_key_obj = None
    user = None
    
    if api_key_header:
        try:
            api_key_obj = APIKey.objects.get(key=api_key_header, is_active=True)
            user = api_key_obj.user
            
            # Проверка доступа к API
            profile = user.profile
            if not profile.plan or not profile.plan.api_access:
                return JsonResponse({'error': 'Ваш план не включает доступ к API'}, status=403)
            
            # Проверка лимитов
            can_verify, message = profile.can_verify()
            if not can_verify:
                return JsonResponse({'error': message}, status=429)
            
            # Обновление статистики API ключа
            api_key_obj.last_used = timezone.now()
            api_key_obj.requests_count += 1
            api_key_obj.save()
            
        except APIKey.DoesNotExist:
            return JsonResponse({'error': 'Неверный API ключ'}, status=401)
    else:
        # Анонимный запрос
        if request.user.is_authenticated:
            user = request.user
            profile, _ = UserProfile.objects.get_or_create(user=user)
            can_verify, message = profile.can_verify()
            if not can_verify:
                return JsonResponse({'error': message}, status=429)
        else:
            can_verify, remaining = check_anonymous_limit(request)
            if not can_verify:
                return JsonResponse({
                    'error': f'Достигнут лимит бесплатных проверок ({ANONYMOUS_DAILY_LIMIT}/день). Зарегистрируйтесь для увеличения лимита.'
                }, status=429)
    
    # Получение email
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
    except json.JSONDecodeError:
        email = request.POST.get('email', '').strip()
    
    if not email:
        return JsonResponse({'error': 'Email не указан'}, status=400)
    
    # Верификация
    result = verify_email(email)
    
    # Сохранение в базу данных
    verification = EmailVerification.objects.create(
        user=user,
        email=email,
        is_valid_syntax=result['is_valid_syntax'],
        has_mx_record=result['has_mx_record'],
        is_deliverable=result['is_deliverable'],
        is_disposable=result['is_disposable'],
        domain=result['domain'],
        mx_records=', '.join(result['mx_records']),
        error_message=result['error_message'],
        ip_address=get_client_ip(request),
        api_key=api_key_obj,
    )
    
    # Обновление счётчика пользователя
    if user:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.increment_usage()
    
    return JsonResponse({
        'success': True,
        'data': result,
        'verification_id': verification.id,
    })


def verify_email_form(request):
    """Обработка формы верификации (для не-AJAX запросов)"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        # Проверка лимитов
        if request.user.is_authenticated:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            can_verify, message = profile.can_verify()
            if not can_verify:
                messages.error(request, message)
                return redirect('money:home')
        else:
            can_verify, remaining = check_anonymous_limit(request)
            if not can_verify:
                messages.error(request, f'Достигнут лимит бесплатных проверок. Зарегистрируйтесь!')
                return redirect('money:home')
        
        if email:
            result = verify_email(email)
            
            user = request.user if request.user.is_authenticated else None
            EmailVerification.objects.create(
                user=user,
                email=email,
                is_valid_syntax=result['is_valid_syntax'],
                has_mx_record=result['has_mx_record'],
                is_deliverable=result['is_deliverable'],
                is_disposable=result['is_disposable'],
                domain=result['domain'],
                mx_records=', '.join(result['mx_records']),
                error_message=result['error_message'],
                ip_address=get_client_ip(request),
            )
            
            if user:
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.increment_usage()
            
            return render(request, 'home/index.html', {'result': result})
    
    return render(request, 'home/index.html')


@login_required
def history(request):
    """История проверок пользователя"""
    verifications = EmailVerification.objects.filter(user=request.user)[:50]
    return render(request, 'home/history.html', {'verifications': verifications})


def pricing(request):
    """Страница с тарифами"""
    plans = SubscriptionPlan.objects.filter(is_active=True)
    return render(request, 'home/pricing.html', {'plans': plans})


@login_required
def dashboard(request):
    """Личный кабинет пользователя"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    api_keys = APIKey.objects.filter(user=request.user)
    recent_verifications = EmailVerification.objects.filter(user=request.user)[:10]
    
    context = {
        'profile': profile,
        'api_keys': api_keys,
        'recent_verifications': recent_verifications,
    }
    return render(request, 'home/dashboard.html', context)


@login_required
def create_api_key(request):
    """Создание нового API ключа"""
    if request.method == 'POST':
        profile = request.user.profile
        
        if not profile.plan or not profile.plan.api_access:
            messages.error(request, 'Ваш план не включает доступ к API')
            return redirect('money:dashboard')
        
        name = request.POST.get('name', 'API Key')
        api_key = APIKey.objects.create(user=request.user, name=name)
        messages.success(request, f'API ключ создан: {api_key.key}')
    
    return redirect('money:dashboard')


@login_required
def delete_api_key(request, key_id):
    """Удаление API ключа"""
    try:
        api_key = APIKey.objects.get(id=key_id, user=request.user)
        api_key.delete()
        messages.success(request, 'API ключ удалён')
    except APIKey.DoesNotExist:
        messages.error(request, 'API ключ не найден')
    
    return redirect('money:dashboard')


@login_required
def subscribe(request, plan_name):
    """Оформление подписки"""
    from django.conf import settings
    from .yookassa_integration import create_payment
    
    try:
        plan = SubscriptionPlan.objects.get(name=plan_name, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, 'План не найден')
        return redirect('money:pricing')
    
    period = request.GET.get('period', 'monthly')
    amount = plan.price_yearly if period == 'yearly' else plan.price_monthly
    
    if amount == 0:
        # Бесплатный план - активируем сразу
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.plan = plan
        profile.subscription_start = timezone.now()
        profile.save()
        messages.success(request, f'План "{plan.display_name}" активирован!')
        return redirect('money:dashboard')
    
    # Проверяем, настроена ли ЮКасса
    use_yookassa = getattr(settings, 'YOOKASSA_SHOP_ID', None) and getattr(settings, 'YOOKASSA_SECRET_KEY', None)
    
    if use_yookassa:
        # Реальная оплата через ЮКассу
        try:
            payment_data = create_payment(
                amount=float(amount),
                description=f'Подписка {plan.display_name} ({"1 год" if period == "yearly" else "1 месяц"})',
                return_url=request.build_absolute_uri('/payment/success/'),
                metadata={
                    'user_id': request.user.id,
                    'plan_id': plan.id,
                    'period': period
                }
            )
            
            # Сохраняем платёж в базу
            Payment.objects.create(
                user=request.user,
                plan=plan,
                amount=amount,
                period_type=period,
                payment_id=payment_data['id'],
                status='pending'
            )
            
            # Редирект на страницу оплаты ЮКасса
            return redirect(payment_data['confirmation_url'])
            
        except Exception as e:
            messages.error(request, f'Ошибка создания платежа: {str(e)}')
            return redirect('money:pricing')
    else:
        # Демо-режим (ЮКасса не настроена)
        payment = Payment.objects.create(
            user=request.user,
            plan=plan,
            amount=amount,
            period_type=period,
        )
        
        return render(request, 'home/checkout.html', {
            'payment': payment,
            'plan': plan,
            'period': period,
        })


def payment_callback(request):
    """Callback от платёжной системы"""
    payment_id = request.GET.get('payment_id')
    
    try:
        payment = Payment.objects.get(payment_id=payment_id)
        
        # В реальном приложении здесь проверка статуса в платёжной системе
        # Для демо - просто активируем
        payment.status = 'completed'
        payment.completed_at = timezone.now()
        payment.save()
        
        # Активируем подписку
        profile, _ = UserProfile.objects.get_or_create(user=payment.user)
        profile.plan = payment.plan
        profile.subscription_start = timezone.now()
        
        if payment.period_type == 'yearly':
            profile.subscription_end = timezone.now() + timedelta(days=365)
        else:
            profile.subscription_end = timezone.now() + timedelta(days=30)
        
        profile.monthly_verifications = 0  # Сброс счётчика
        profile.save()
        
        messages.success(request, 'Оплата прошла успешно! Подписка активирована.')
        return redirect('money:dashboard')
        
    except Payment.DoesNotExist:
        messages.error(request, 'Платёж не найден')
        return redirect('money:pricing')


# Регистрация и авторизация
@ratelimit(key='ip', rate='10/m', method='POST', block=True)  # 10 попыток регистрации в минуту
def register_view(request):
    """Регистрация пользователя"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        
        if password != password2:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'home/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return render(request, 'home/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Пользователь с таким email уже существует')
            return render(request, 'home/register.html')
        
        user = User.objects.create_user(username=username, email=email, password=password)
        
        # Создаём профиль с бесплатным планом
        free_plan = SubscriptionPlan.objects.filter(name='free').first()
        UserProfile.objects.create(user=user, plan=free_plan)
        
        login(request, user)
        messages.success(request, 'Регистрация успешна!')
        return redirect('money:dashboard')
    
    return render(request, 'home/register.html')


@ratelimit(key='ip', rate='5/m', method='POST', block=True)  # 5 попыток входа в минуту (защита от брутфорса)
def login_view(request):
    """Авторизация пользователя"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('money:dashboard')
        else:
            messages.error(request, 'Неверный логин или пароль')
    
    return render(request, 'home/login.html')


def logout_view(request):
    """Выход из системы"""
    logout(request)
    return redirect('money:home')


def ratelimit_error(request, exception):
    """Обработчик ошибки rate limit"""
    return JsonResponse({
        'error': 'Слишком много запросов. Пожалуйста, подождите немного.',
        'retry_after': 60
    }, status=429)


@csrf_exempt
def yookassa_webhook(request):
    """
    Webhook для получения уведомлений от ЮКасса.
    Настройте URL в личном кабинете ЮКасса:
    https://yourdomain.com/payment/webhook/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        from .yookassa_integration import process_webhook
        
        data = process_webhook(request.body)
        
        if data['status'] == 'succeeded':
            # Находим платёж
            try:
                payment = Payment.objects.get(payment_id=data['payment_id'])
                
                if payment.status != 'completed':  # Избегаем повторной обработки
                    payment.status = 'completed'
                    payment.completed_at = timezone.now()
                    payment.save()
                    
                    # Активируем подписку
                    profile, _ = UserProfile.objects.get_or_create(user=payment.user)
                    profile.plan = payment.plan
                    profile.subscription_start = timezone.now()
                    
                    if payment.period_type == 'yearly':
                        profile.subscription_end = timezone.now() + timedelta(days=365)
                    else:
                        profile.subscription_end = timezone.now() + timedelta(days=30)
                    
                    profile.monthly_verifications = 0
                    profile.save()
                    
            except Payment.DoesNotExist:
                pass  # Платёж не найден
        
        elif data['status'] == 'canceled':
            try:
                payment = Payment.objects.get(payment_id=data['payment_id'])
                payment.status = 'failed'
                payment.save()
            except Payment.DoesNotExist:
                pass
        
        return JsonResponse({'status': 'ok'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def payment_success(request):
    """Страница успешной оплаты"""
    messages.success(request, 'Оплата прошла успешно! Подписка активирована.')
    return redirect('money:dashboard')
