from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
import json

from .models import EmailVerification, SubscriptionPlan, UserProfile, APIKey, Payment
from .views import (
    validate_email_syntax, 
    get_domain, 
    is_disposable_email, 
    verify_email,
    check_mx_records,
)


class EmailSyntaxValidationTests(TestCase):
    """Тесты валидации синтаксиса email"""
    
    def test_valid_emails(self):
        """Проверка валидных email адресов"""
        valid_emails = [
            'test@example.com',
            'user.name@domain.org',
            'user+tag@gmail.com',
            'user123@sub.domain.co.uk',
            'a@b.cc',
        ]
        for email in valid_emails:
            self.assertTrue(validate_email_syntax(email), f"{email} should be valid")
    
    def test_invalid_emails(self):
        """Проверка невалидных email адресов"""
        invalid_emails = [
            'invalid',
            '@domain.com',
            'user@',
            'user@.com',
            'user@domain',
            'user name@domain.com',
            '',
            'user@@domain.com',
        ]
        for email in invalid_emails:
            self.assertFalse(validate_email_syntax(email), f"{email} should be invalid")


class DomainExtractionTests(TestCase):
    """Тесты извлечения домена"""
    
    def test_get_domain(self):
        self.assertEqual(get_domain('user@example.com'), 'example.com')
        self.assertEqual(get_domain('test@sub.domain.org'), 'sub.domain.org')
        self.assertEqual(get_domain('invalid'), '')


class DisposableEmailTests(TestCase):
    """Тесты определения одноразовых email"""
    
    def test_disposable_domains(self):
        """Проверка одноразовых доменов"""
        disposable = ['tempmail.com', 'guerrillamail.com', 'mailinator.com', 'yopmail.com']
        for domain in disposable:
            self.assertTrue(is_disposable_email(domain), f"{domain} should be disposable")
    
    def test_normal_domains(self):
        """Проверка обычных доменов"""
        normal = ['gmail.com', 'yahoo.com', 'outlook.com', 'company.org']
        for domain in normal:
            self.assertFalse(is_disposable_email(domain), f"{domain} should not be disposable")


class EmailVerificationLogicTests(TestCase):
    """Тесты логики верификации email"""
    
    def test_invalid_syntax_returns_invalid_status(self):
        """Невалидный синтаксис возвращает статус invalid"""
        result = verify_email('invalid-email')
        self.assertEqual(result['status'], 'invalid')
        self.assertFalse(result['is_valid_syntax'])
        self.assertEqual(result['score'], 0)
    
    @patch('money.views.check_mx_records')
    def test_no_mx_records_returns_invalid(self, mock_mx):
        """Отсутствие MX-записей возвращает invalid"""
        mock_mx.return_value = (False, [])
        result = verify_email('user@nonexistent-domain-xyz.com')
        self.assertEqual(result['status'], 'invalid')
        self.assertFalse(result['has_mx_record'])
    
    @patch('money.views.check_mx_records')
    @patch('money.views.check_smtp_deliverable')
    def test_valid_email_returns_valid_status(self, mock_smtp, mock_mx):
        """Валидный email возвращает статус valid"""
        mock_mx.return_value = (True, ['mx.example.com'])
        mock_smtp.return_value = True
        
        result = verify_email('user@example.com')
        self.assertEqual(result['status'], 'valid')
        self.assertTrue(result['is_deliverable'])
        self.assertEqual(result['score'], 100)
    
    @patch('money.views.check_mx_records')
    @patch('money.views.check_smtp_deliverable')
    def test_unknown_deliverability_returns_unknown(self, mock_smtp, mock_mx):
        """Неизвестная доставляемость возвращает unknown"""
        mock_mx.return_value = (True, ['mx.example.com'])
        mock_smtp.return_value = None  # Сервер не ответил
        
        result = verify_email('user@example.com')
        self.assertEqual(result['status'], 'unknown')
        self.assertTrue(result['is_deliverable_unknown'])
        self.assertEqual(result['score'], 80)  # 25 + 25 + 20 + 10 (not disposable)
    
    @patch('money.views.check_mx_records')
    @patch('money.views.check_smtp_deliverable')
    def test_disposable_email_returns_risky(self, mock_smtp, mock_mx):
        """Одноразовый email возвращает risky"""
        mock_mx.return_value = (True, ['mx.tempmail.com'])
        mock_smtp.return_value = True
        
        result = verify_email('user@tempmail.com')
        self.assertEqual(result['status'], 'risky')
        self.assertTrue(result['is_disposable'])


class SubscriptionPlanModelTests(TestCase):
    """Тесты модели тарифных планов"""
    
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            name='test',
            display_name='Test Plan',
            price_monthly=100,
            daily_limit=10,
            monthly_limit=100,
            api_access=True,
        )
    
    def test_plan_creation(self):
        self.assertEqual(self.plan.name, 'test')
        self.assertEqual(self.plan.daily_limit, 10)
        self.assertTrue(self.plan.api_access)
    
    def test_plan_str(self):
        self.assertEqual(str(self.plan), 'Test Plan')


class UserProfileModelTests(TestCase):
    """Тесты модели профиля пользователя"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
        self.plan = SubscriptionPlan.objects.create(
            name='free',
            display_name='Free',
            daily_limit=5,
            monthly_limit=100,
        )
        self.profile = UserProfile.objects.create(user=self.user, plan=self.plan)
    
    def test_can_verify_within_limits(self):
        """Проверка возможности верификации в пределах лимитов"""
        can_verify, message = self.profile.can_verify()
        self.assertTrue(can_verify)
    
    def test_cannot_verify_over_daily_limit(self):
        """Проверка блокировки при превышении дневного лимита"""
        from datetime import date
        self.profile.daily_verifications = 5
        self.profile.last_verification_date = date.today()  # Устанавливаем сегодняшнюю дату
        self.profile.save()
        
        can_verify, message = self.profile.can_verify()
        self.assertFalse(can_verify)
        self.assertIn('дневной лимит', message.lower())
    
    def test_increment_usage(self):
        """Проверка увеличения счётчиков"""
        initial_daily = self.profile.daily_verifications
        initial_total = self.profile.total_verifications
        
        self.profile.increment_usage()
        
        self.assertEqual(self.profile.daily_verifications, initial_daily + 1)
        self.assertEqual(self.profile.total_verifications, initial_total + 1)


class APIKeyModelTests(TestCase):
    """Тесты модели API ключей"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
    
    def test_api_key_auto_generation(self):
        """Проверка автоматической генерации ключа"""
        api_key = APIKey.objects.create(user=self.user, name='Test Key')
        self.assertIsNotNone(api_key.key)
        self.assertEqual(len(api_key.key), 64)  # 32 bytes hex = 64 chars


class EmailVerificationModelTests(TestCase):
    """Тесты модели проверки email"""
    
    def test_overall_score_calculation(self):
        """Проверка расчёта общего балла"""
        verification = EmailVerification.objects.create(
            email='test@example.com',
            is_valid_syntax=True,
            has_mx_record=True,
            is_deliverable=True,
            is_disposable=False,
        )
        self.assertEqual(verification.overall_score, 100)
    
    def test_overall_score_partial(self):
        """Проверка частичного балла"""
        verification = EmailVerification.objects.create(
            email='test@example.com',
            is_valid_syntax=True,
            has_mx_record=True,
            is_deliverable=False,
            is_disposable=True,
        )
        self.assertEqual(verification.overall_score, 50)  # 25 + 25 + 0 + 0


class ViewsTests(TestCase):
    """Тесты представлений"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
        self.plan = SubscriptionPlan.objects.create(
            name='free',
            display_name='Free',
            daily_limit=5,
            monthly_limit=100,
            api_access=False,
        )
        UserProfile.objects.create(user=self.user, plan=self.plan)
    
    def test_home_page_loads(self):
        """Главная страница загружается"""
        response = self.client.get(reverse('money:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email Верификатор')
    
    def test_pricing_page_loads(self):
        """Страница тарифов загружается"""
        response = self.client.get(reverse('money:pricing'))
        self.assertEqual(response.status_code, 200)
    
    def test_login_page_loads(self):
        """Страница входа загружается"""
        response = self.client.get(reverse('money:login'))
        self.assertEqual(response.status_code, 200)
    
    def test_register_page_loads(self):
        """Страница регистрации загружается"""
        response = self.client.get(reverse('money:register'))
        self.assertEqual(response.status_code, 200)
    
    def test_dashboard_requires_login(self):
        """Личный кабинет требует авторизации"""
        response = self.client.get(reverse('money:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_dashboard_accessible_when_logged_in(self):
        """Личный кабинет доступен после входа"""
        self.client.login(username='testuser', password='password')
        response = self.client.get(reverse('money:dashboard'))
        self.assertEqual(response.status_code, 200)
    
    def test_history_requires_login(self):
        """История требует авторизации"""
        response = self.client.get(reverse('money:history'))
        self.assertEqual(response.status_code, 302)


class APITests(TestCase):
    """Тесты API"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
        self.plan = SubscriptionPlan.objects.create(
            name='pro',
            display_name='Pro',
            daily_limit=100,
            monthly_limit=1000,
            api_access=True,
        )
        self.profile = UserProfile.objects.create(user=self.user, plan=self.plan)
        self.api_key = APIKey.objects.create(user=self.user, name='Test Key')
    
    @patch('money.views.verify_email')
    def test_api_verify_with_valid_key(self, mock_verify):
        """API работает с валидным ключом"""
        mock_verify.return_value = {
            'email': 'test@example.com',
            'is_valid_syntax': True,
            'has_mx_record': True,
            'is_deliverable': True,
            'is_deliverable_unknown': False,
            'is_disposable': False,
            'domain': 'example.com',
            'mx_records': ['mx.example.com'],
            'error_message': '',
            'score': 100,
            'status': 'valid',
        }
        
        response = self.client.post(
            reverse('money:verify_api'),
            data=json.dumps({'email': 'test@example.com'}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
    
    def test_api_verify_with_invalid_key(self):
        """API отклоняет невалидный ключ"""
        response = self.client.post(
            reverse('money:verify_api'),
            data=json.dumps({'email': 'test@example.com'}),
            content_type='application/json',
            HTTP_X_API_KEY='invalid-key'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_api_verify_without_email(self):
        """API требует email"""
        response = self.client.post(
            reverse('money:verify_api'),
            data=json.dumps({}),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key
        )
        
        self.assertEqual(response.status_code, 400)


class RegistrationTests(TestCase):
    """Тесты регистрации"""
    
    def setUp(self):
        self.client = Client()
        SubscriptionPlan.objects.create(
            name='free',
            display_name='Free',
            daily_limit=5,
            monthly_limit=100,
        )
    
    def test_successful_registration(self):
        """Успешная регистрация"""
        response = self.client.post(reverse('money:register'), {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'testpass123',
            'password2': 'testpass123',
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_registration_password_mismatch(self):
        """Регистрация с несовпадающими паролями"""
        response = self.client.post(reverse('money:register'), {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'testpass123',
            'password2': 'differentpass',
        })
        
        self.assertEqual(response.status_code, 200)  # Stay on page
        self.assertFalse(User.objects.filter(username='newuser').exists())


class LoginTests(TestCase):
    """Тесты авторизации"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
    
    def test_successful_login(self):
        """Успешный вход"""
        response = self.client.post(reverse('money:login'), {
            'username': 'testuser',
            'password': 'password',
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
    
    def test_failed_login(self):
        """Неудачный вход"""
        response = self.client.post(reverse('money:login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        
        self.assertEqual(response.status_code, 200)  # Stay on page


class PaymentTests(TestCase):
    """Тесты платежей"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'password')
        self.plan = SubscriptionPlan.objects.create(
            name='basic',
            display_name='Basic',
            price_monthly=490,
            daily_limit=50,
            monthly_limit=1000,
        )
        UserProfile.objects.create(user=self.user)
        self.client.login(username='testuser', password='password')
    
    def test_subscribe_creates_payment(self):
        """Подписка создаёт платёж"""
        response = self.client.get(reverse('money:subscribe', args=['basic']))
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Payment.objects.filter(user=self.user, plan=self.plan).exists())
    
    def test_payment_callback_activates_subscription(self):
        """Callback активирует подписку"""
        payment = Payment.objects.create(
            user=self.user,
            plan=self.plan,
            amount=490,
        )
        
        response = self.client.get(
            reverse('money:payment_callback'),
            {'payment_id': payment.payment_id}
        )
        
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
        
        profile = self.user.profile
        profile.refresh_from_db()
        self.assertEqual(profile.plan, self.plan)
