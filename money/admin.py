from django.contrib import admin
from .models import EmailVerification, SubscriptionPlan, UserProfile, APIKey, Payment, YooKassaSettings


@admin.register(YooKassaSettings)
class YooKassaSettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_active', 'shop_id', 'created_at', 'updated_at']
    fieldsets = (
        ('Основные настройки', {
            'fields': ('shop_id', 'secret_key', 'is_active')
        }),
        ('Webhook', {
            'fields': ('webhook_url', 'webhook_secret'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'price_monthly', 'daily_limit', 'monthly_limit', 'api_access', 'is_active']
    list_filter = ['is_active', 'api_access']
    search_fields = ['name', 'display_name']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'daily_verifications', 'monthly_verifications', 'total_verifications']
    list_filter = ['plan']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'key', 'is_active', 'requests_count', 'last_used', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'user__username', 'key']
    raw_id_fields = ['user']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'plan', 'amount', 'currency', 'status', 'period_type', 'payment_id', 'created_at', 'completed_at']
    list_filter = ['status', 'period_type', 'plan']
    search_fields = ['user__username', 'payment_id']
    raw_id_fields = ['user', 'plan']
    readonly_fields = ['payment_id', 'created_at', 'completed_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Плательщик', {
            'fields': ('user', 'plan')
        }),
        ('Сумма', {
            'fields': ('amount', 'currency', 'period_type')
        }),
        ('Статус', {
            'fields': ('status', 'payment_method')
        }),
        ('Даты', {
            'fields': ('created_at', 'completed_at')
        }),
    )

    actions = ['mark_as_completed', 'mark_as_failed', 'refund_payment']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} платежей отмечено как оплаченные')
    mark_as_completed.short_description = 'Отметить как оплаченные'
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} платежей отмечено как ошибка')
    mark_as_failed.short_description = 'Отметить как ошибка'
    
    def refund_payment(self, request, queryset):
        updated = queryset.update(status='refunded')
        self.message_user(request, f'{updated} платежей отмечено как возврат')
    refund_payment.short_description = 'Отметить как возврат'


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'user', 'is_valid_syntax', 'has_mx_record', 'is_deliverable', 'is_disposable', 'created_at']
    list_filter = ['is_valid_syntax', 'has_mx_record', 'is_deliverable', 'is_disposable']
    search_fields = ['email', 'domain', 'user__username']
    raw_id_fields = ['user', 'api_key']
    date_hierarchy = 'created_at'
