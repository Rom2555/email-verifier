from django.urls import path
from . import views

app_name = 'money'

urlpatterns = [
    # Главная и верификация
    path('', views.home, name='home'),
    path('verify/', views.verify_email_form, name='verify'),
    path('api/verify/', views.verify_email_api, name='verify_api'),
    path('history/', views.history, name='history'),
    
    # Тарифы и оплата
    path('pricing/', views.pricing, name='pricing'),
    path('subscribe/<str:plan_name>/', views.subscribe, name='subscribe'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('payment/webhook/', views.yookassa_webhook, name='yookassa_webhook'),
    path('payment/success/', views.payment_success, name='payment_success'),
    
    # Личный кабинет
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api-keys/create/', views.create_api_key, name='create_api_key'),
    path('api-keys/delete/<int:key_id>/', views.delete_api_key, name='delete_api_key'),
    
    # Авторизация
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
