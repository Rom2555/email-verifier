# Email Verifier

Веб-сервис для верификации email адресов с API.

## Возможности

- ✅ Проверка синтаксиса email
- ✅ Проверка MX-записей домена
- ✅ Проверка существования почтового ящика (SMTP)
- ✅ Определение одноразовых email (temp-mail)
- 💰 Тарифные планы с лимитами
- 🔑 API для интеграции
- 📊 Личный кабинет

## Быстрый старт

### Локальная разработка

```bash
# Клонирование репозитория
git clone https://github.com/Rom2555/email-verifier.git
cd email-verifier

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка локальных переменных
cp local_settings_example.py local_settings.py
# Отредактируйте local_settings.py и заполните SECRET_KEY

# Миграции базы данных
python manage.py migrate

# Запуск сервера
python manage.py runserver
```

Откройте http://localhost:8000 в браузере.

### Docker (опционально)

```bash
docker-compose up -d
```

## API

### Верификация email

```python
import requests

response = requests.post(
    "http://localhost:8000/api/verify/",
    headers={"X-API-Key": "ВАШ_API_КЛЮЧ"},
    json={"email": "test@example.com"}
)
print(response.json())
```

**Ответ:**

```json
{
    "success": true,
    "data": {
        "email": "test@example.com",
        "is_valid_syntax": true,
        "has_mx_record": true,
        "is_deliverable": true,
        "is_disposable": false,
        "score": 90,
        "status": "valid"
    },
    "verification_id": 1
}
```

## Тарифные планы

| План | Лимит в день | Лимит в месяц | API | Цена |
|------|--------------|---------------|-----|------|
| Free | 5 | 100 | ❌ | 0 ₽ |
| Basic | 50 | 1000 | ✅ | 490 ₽/мес |
| Pro | 200 | 5000 | ✅ | 990 ₽/мес |
| Business | 1000 | 20000 | ✅ | 2490 ₽/мес |

## Развёртывание на сервере

См. [deploy/README.md](deploy/README.md) для подробной инструкции по production развёртыванию.

## Технологии

- Django 4.2+
- PostgreSQL
- Redis
- YooKassa (платежи)
- Nginx
- Gunicorn

## Лицензия

MIT
