from django.core.management.base import BaseCommand
from money.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Setup subscription plans'

    def handle(self, *args, **options):
        plans_data = [
            {
                'name': 'free',
                'display_name': 'Free',
                'price_monthly': 0,
                'price_yearly': 0,
                'daily_limit': 5,
                'monthly_limit': 100,
                'api_access': False,
                'bulk_verification': False,
                'priority_support': False,
                'description': 'Perfect for getting started',
                'features': ['5 checks per day', '100 checks per month', 'Basic verification'],
            },
            {
                'name': 'basic',
                'display_name': 'Basic',
                'price_monthly': 490,
                'price_yearly': 4704,
                'daily_limit': 50,
                'monthly_limit': 1000,
                'api_access': True,
                'bulk_verification': False,
                'priority_support': False,
                'description': 'For individual users',
                'features': ['50 checks per day', '1000 checks per month', 'API access'],
            },
            {
                'name': 'pro',
                'display_name': 'Professional',
                'price_monthly': 1490,
                'price_yearly': 14304,
                'daily_limit': 200,
                'monthly_limit': 5000,
                'api_access': True,
                'bulk_verification': True,
                'priority_support': False,
                'description': 'For professionals and teams',
                'features': ['200 checks per day', '5000 checks per month', 'API access', 'Bulk verification'],
            },
            {
                'name': 'business',
                'display_name': 'Business',
                'price_monthly': 4990,
                'price_yearly': 47904,
                'daily_limit': 1000,
                'monthly_limit': 50000,
                'api_access': True,
                'bulk_verification': True,
                'priority_support': True,
                'description': 'For large companies',
                'features': ['1000 checks per day', '50000 checks per month', 'Full API access', 'Priority support'],
            },
        ]

        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            status = 'created' if created else 'updated'
            self.stdout.write(self.style.SUCCESS(f"Plan '{plan.display_name}' {status}"))

        self.stdout.write(self.style.SUCCESS('All plans setup successfully!'))
