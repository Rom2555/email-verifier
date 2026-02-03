# Email Verifier — Руководство по развёртыванию

## 🖥️ Локальная разработка

```bash
# Клонирование репозитория
git clone https://github.com/Rom2555/email-verifier.git
cd email-verifier

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # или .venv\Scripts\activate на Windows

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

---

## 🚀 Быстрый старт (Production)

### 1. Требования к серверу
- Ubuntu 20.04+ / Debian 11+
- Python 3.10+
- PostgreSQL 13+
- Redis 6+
- Nginx
- Certbot (для SSL)

### 2. Установка зависимостей

```bash
# Системные пакеты
sudo apt update
sudo apt install python3-pip python3-venv postgresql postgresql-contrib redis-server nginx certbot python3-certbot-nginx fail2ban

# Создание директории проекта
sudo mkdir -p /var/www/email-verifier
sudo chown $USER:$USER /var/www/email-verifier
cd /var/www/email-verifier

# Клонирование проекта
git clone <your-repo> .

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### 3. Настройка PostgreSQL

```bash
sudo -u postgres psql

CREATE DATABASE email_verifier;
CREATE USER email_user WITH PASSWORD 'your-secure-password';
ALTER ROLE email_user SET client_encoding TO 'utf8';
ALTER ROLE email_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE email_user SET timezone TO 'Europe/Moscow';
GRANT ALL PRIVILEGES ON DATABASE email_verifier TO email_user;
\q
```

### 4. Настройка Redis

```bash
sudo nano /etc/redis/redis.conf

# Установка пароля
requirepass your-redis-password

# Перезапуск Redis
sudo systemctl restart redis
```

### 5. Переменные окружения

```bash
# Создание файла .env
cat > .env << EOF
DJANGO_SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_NAME=email_verifier
DB_USER=email_user
DB_PASSWORD=your-secure-password
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://127.0.0.1:6379/1
REDIS_PASSWORD=your-redis-password
EOF

# Загрузка переменных окружения
export $(cat .env | xargs)
```

### 6. Настройка Django

```bash
# Использование production настроек
export DJANGO_SETTINGS_MODULE=mon_project.settings_production

# Миграции базы данных
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Настройка тарифных планов
python manage.py setup_plans

# Сбор статических файлов
python manage.py collectstatic --noinput
```

### 7. Настройка Nginx

```bash
# Копирование конфига nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/email-verifier

# Редактирование имени домена
sudo nano /etc/nginx/sites-available/email-verifier

# Включение сайта
sudo ln -s /etc/nginx/sites-available/email-verifier /etc/nginx/sites-enabled/

# Проверка конфигурации
sudo nginx -t

# Получение SSL-сертификата
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Перезапуск nginx
sudo systemctl restart nginx
```

### 8. Настройка Fail2ban

```bash
# Копирование фильтра
sudo cp deploy/fail2ban-filter.conf /etc/fail2ban/filter.d/email-verifier.conf

# Добавление jail в jail.local
sudo cat deploy/fail2ban-jail.conf >> /etc/fail2ban/jail.local

# Перезапуск fail2ban
sudo systemctl restart fail2ban
```

### 9. Создание systemd-сервиса

```bash
sudo nano /etc/systemd/system/email-verifier.service
```

```ini
[Unit]
Description=Email Verifier Django App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/email-verifier
Environment="DJANGO_SETTINGS_MODULE=mon_project.settings_production"
EnvironmentFile=/var/www/email-verifier/.env
ExecStart=/var/www/email-verifier/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 mon_project.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Включение и запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable email-verifier
sudo systemctl start email-verifier
```

### 10. Проверка развёртывания

```bash
# Статус сервиса
sudo systemctl status email-verifier

# Статус nginx
sudo systemctl status nginx

# Статус fail2ban
sudo fail2ban-client status email-verifier

# Тестирование rate limiting
for i in {1..35}; do curl -X POST https://yourdomain.com/api/verify/ -d '{"email":"test@test.com"}'; done
```

---

## 🔒 Чек-лист безопасности

- [ ] SSL-сертификат установлен (Let's Encrypt)
- [ ] DEBUG = False в production
- [ ] SECRET_KEY из переменной окружения
- [ ] PostgreSQL с надёжным паролем
- [ ] Redis с паролем
- [ ] Rate limiting в Nginx настроен
- [ ] Fail2ban активен
- [ ] Настроен firewall (ufw)
- [ ] Настроены регулярные бэкапы

## 📊 Мониторинг

```bash
# Просмотр логов приложения
sudo journalctl -u email-verifier -f

# Просмотр access логов nginx
sudo tail -f /var/log/nginx/email-verifier.access.log

# Просмотр забаненных IP в fail2ban
sudo fail2ban-client status email-verifier
```

## 🔄 Обновления

```bash
cd /var/www/email-verifier
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart email-verifier
```
