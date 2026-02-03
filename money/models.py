from django.db import models
from django.contrib.auth.models import User
import secrets
import uuid


class YooKassaSettings(models.Model):
    """Настройки ЮKassa"""
    
    shop_id = models.CharField(max_length=100, blank=True, verbose_name="Shop ID")
    secret_key = models.CharField(max_length=255, blank=True, verbose_name="Secret Key")
    
    is_active = models.BooleanField(default=False, verbose_name="Активен")
    
    webhook_url = models.CharField(max_length=255, blank=True, verbose_name="Webhook URL")
    webhook_secret = models.CharField(max_length=255, blank=True, verbose_name="Webhook Secret")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Настройки ЮKassa"
        verbose_name_plural = "Настройки ЮKassa"
    
    def __str__(self):
        return f"ЮKassa {'(активен)' if self.is_active else '(неактивен)'}"


class SubscriptionPlan(models.Model):
    """Тарифные планы"""
    
    PLAN_CHOICES = [
        ('free', 'Бесплатный'),
        ('basic', 'Базовый'),
        ('pro', 'Профессиональный'),
        ('business', 'Бизнес'),
    ]
    
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True, verbose_name="Название")
    display_name = models.CharField(max_length=100, verbose_name="Отображаемое название")
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена в месяц (руб)")
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена в год (руб)")
    
    # Лимиты
    daily_limit = models.IntegerField(default=5, verbose_name="Лимит проверок в день")
    monthly_limit = models.IntegerField(default=100, verbose_name="Лимит проверок в месяц")
    api_access = models.BooleanField(default=False, verbose_name="Доступ к API")
    bulk_verification = models.BooleanField(default=False, verbose_name="Массовая проверка")
    priority_support = models.BooleanField(default=False, verbose_name="Приоритетная поддержка")
    
    # Описание
    description = models.TextField(blank=True, verbose_name="Описание")
    features = models.JSONField(default=list, verbose_name="Список функций")
    
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    class Meta:
        verbose_name = "Тарифный план"
        verbose_name_plural = "Тарифные планы"
        ordering = ['price_monthly']
    
    def __str__(self):
        return self.display_name


class UserProfile(models.Model):
    """Профиль пользователя с подпиской"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Тарифный план")
    
    # Счётчики использования
    daily_verifications = models.IntegerField(default=0, verbose_name="Проверок сегодня")
    monthly_verifications = models.IntegerField(default=0, verbose_name="Проверок в этом месяце")
    total_verifications = models.IntegerField(default=0, verbose_name="Всего проверок")
    
    # Даты
    last_verification_date = models.DateField(null=True, blank=True, verbose_name="Дата последней проверки")
    subscription_start = models.DateTimeField(null=True, blank=True, verbose_name="Начало подписки")
    subscription_end = models.DateTimeField(null=True, blank=True, verbose_name="Окончание подписки")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    
    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.display_name if self.plan else 'Без плана'}"
    
    def can_verify(self):
        """Проверка, может ли пользователь делать проверки"""
        from datetime import date
        
        # Сброс дневного счётчика
        if self.last_verification_date != date.today():
            self.daily_verifications = 0
            self.last_verification_date = date.today()
            self.save()
        
        if not self.plan:
            return False, "Выберите тарифный план"
        
        if self.daily_verifications >= self.plan.daily_limit:
            return False, f"Достигнут дневной лимит ({self.plan.daily_limit} проверок)"
        
        if self.monthly_verifications >= self.plan.monthly_limit:
            return False, f"Достигнут месячный лимит ({self.plan.monthly_limit} проверок)"
        
        return True, "OK"
    
    def increment_usage(self):
        """Увеличить счётчик использования"""
        from datetime import date
        
        if self.last_verification_date != date.today():
            self.daily_verifications = 0
            self.last_verification_date = date.today()
        
        self.daily_verifications += 1
        self.monthly_verifications += 1
        self.total_verifications += 1
        self.save()


class APIKey(models.Model):
    """API ключи для программного доступа"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys', verbose_name="Пользователь")
    key = models.CharField(max_length=64, unique=True, verbose_name="API ключ")
    name = models.CharField(max_length=100, verbose_name="Название ключа")
    
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    last_used = models.DateTimeField(null=True, blank=True, verbose_name="Последнее использование")
    
    # Статистика
    requests_count = models.IntegerField(default=0, verbose_name="Количество запросов")
    
    class Meta:
        verbose_name = "API ключ"
        verbose_name_plural = "API ключи"
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)


class Payment(models.Model):
    """История платежей"""
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('completed', 'Оплачен'),
        ('failed', 'Ошибка'),
        ('refunded', 'Возврат'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments', verbose_name="Пользователь")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, verbose_name="Тарифный план")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма")
    currency = models.CharField(max_length=3, default='RUB', verbose_name="Валюта")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    
    # Данные платёжной системы
    payment_id = models.CharField(max_length=100, unique=True, verbose_name="ID платежа")
    payment_method = models.CharField(max_length=50, blank=True, verbose_name="Способ оплаты")
    
    # Период подписки
    period_type = models.CharField(max_length=10, choices=[('monthly', 'Месяц'), ('yearly', 'Год')], default='monthly')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата оплаты")
    
    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} {self.currency} - {self.status}"
    
    def save(self, *args, **kwargs):
        if not self.payment_id:
            self.payment_id = str(uuid.uuid4())
        super().save(*args, **kwargs)


class EmailVerification(models.Model):
    """Модель для хранения результатов проверки email"""
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verifications', verbose_name="Пользователь")
    email = models.EmailField(verbose_name="Email адрес")
    
    # Результаты проверки
    is_valid_syntax = models.BooleanField(default=False, verbose_name="Валидный синтаксис")
    has_mx_record = models.BooleanField(default=False, verbose_name="Есть MX-запись")
    is_deliverable = models.BooleanField(default=False, verbose_name="Доставляемый")
    is_disposable = models.BooleanField(default=False, verbose_name="Одноразовый email")
    
    # Дополнительная информация
    domain = models.CharField(max_length=255, blank=True, verbose_name="Домен")
    mx_records = models.TextField(blank=True, verbose_name="MX-записи")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата проверки")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP адрес")
    api_key = models.ForeignKey(APIKey, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="API ключ")
    
    class Meta:
        verbose_name = "Проверка email"
        verbose_name_plural = "Проверки email"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email} - {'✓' if self.is_deliverable else '✗'}"
    
    @property
    def overall_score(self):
        """Общий балл качества email (0-100)"""
        score = 0
        if self.is_valid_syntax:
            score += 25
        if self.has_mx_record:
            score += 25
        if self.is_deliverable:
            score += 40
        if not self.is_disposable:
            score += 10
        return score
