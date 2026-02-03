"""
Скрипт для создания начальных тарифных планов.
Запуск: python manage.py shell < money/setup_plans.py
"""

from money.models import SubscriptionPlan

# Создаём тарифные планы
plans_data = [
    {
        'name': 'free',
        'display_name': 'Бесплатный',
        'price_monthly': 0,
        'price_yearly': 0,
        'daily_limit': 5,
        'monthly_limit': 100,
        'api_access': False,
        'bulk_verification': False,
        'priority_support': False,
        'description': 'Идеально для начала работы',
        'features': [
            '5 проверок в день',
            '100 проверок в месяц',
            'Базовая верификация',
        ],
    },
    {
        'name': 'basic',
        'display_name': 'Базовый',
        'price_monthly': 490,
        'price_yearly': 4704,
        'daily_limit': 50,
        'monthly_limit': 1000,
        'api_access': True,
        'bulk_verification': False,
        'priority_support': False,
        'description': 'Для индивидуальных пользователей',
        'features': [
            '50 проверок в день',
            '1 000 проверок в месяц',
            'Доступ к API',
            'Email поддержка',
        ],
    },
    {
        'name': 'pro',
        'display_name': 'Профессиональный',
        'price_monthly': 1490,
        'price_yearly': 14304,
        'daily_limit': 200,
        'monthly_limit': 5000,
        'api_access': True,
        'bulk_verification': True,
        'priority_support': False,
        'description': 'Для профессионалов и команд',
        'features': [
            '200 проверок в день',
            '5 000 проверок в месяц',
            'Доступ к API',
            'Массовая проверка',
            'Приоритетная поддержка',
        ],
    },
    {
        'name': 'business',
        'display_name': 'Бизнес',
        'price_monthly': 4990,
        'price_yearly': 47904,
        'daily_limit': 1000,
        'monthly_limit': 50000,
        'api_access': True,
        'bulk_verification': True,
        'priority_support': True,
        'description': 'Для крупных компаний',
        'features': [
            'До 1 000 проверок в день',
            '50 000 проверок в месяц',
            'Полный доступ к API',
            'Массовая проверка',
            'Приоритетная поддержка 24/7',
            'Выделенный менеджер',
        ],
    },
]

for plan_data in plans_data:
    plan, created = SubscriptionPlan.objects.update_or_create(
        name=plan_data['name'],
        defaults=plan_data
    )
    status = 'создан' if created else 'обновлён'
    print(f"План '{plan.display_name}' {status}")

print("\nВсе планы успешно настроены!")
