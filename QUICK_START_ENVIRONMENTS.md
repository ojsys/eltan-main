# Quick Start Guide - Development vs Production

## TL;DR - Quick Commands

### For Development (Local)

```bash
# 1. Set up environment
cp .env.development .env
export ELTAN_ENV=development

# 2. Install dependencies
pip install -r requirements/development.txt

# 3. Run migrations
python manage.py migrate

# 4. Run server
python manage.py runserver
```

### For Production (cPanel)

```bash
# 1. Set up environment
cp .env.production .env
# Edit .env with your actual credentials!
export ELTAN_ENV=production

# 2. Install dependencies
pip install -r requirements/production.txt

# 3. Run migrations and collect static
python manage.py migrate
python manage.py collectstatic --noinput

# 4. Restart application in cPanel
```

## Key Differences

| Feature | Development | Production |
|---------|-------------|------------|
| Database | SQLite (auto) | MySQL (configure .env) |
| Debug Mode | ON | OFF |
| Email | Console | SMTP |
| Paystack | Test keys | Live keys |
| Security | Relaxed | Enforced |

## Environment Files

- `.env.development` → Development settings (SQLite, test keys)
- `.env.production` → Production settings (MySQL, live keys)
- `.env` → Active file (copy from above)

## Switching Environments

Change the `ELTAN_ENV` variable:

```bash
# Development
export ELTAN_ENV=development

# Production
export ELTAN_ENV=production
```

Or use the settings directly:

```bash
python manage.py runserver --settings=eltanweb.settings.development
python manage.py runserver --settings=eltanweb.settings.production
```

## Common Commands

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files (production)
python manage.py collectstatic

# Run tests
python manage.py test

# Django shell
python manage.py shell
```

## Project Structure

```
eltan2/
├── eltanweb/
│   ├── settings/
│   │   ├── base.py              # Common settings
│   │   ├── development.py       # Dev settings
│   │   └── production.py        # Prod settings
│   ├── wsgi.py
│   └── asgi.py
├── requirements/
│   ├── base.txt                 # Common packages
│   ├── development.txt          # Dev packages
│   └── production.txt           # Prod packages
├── .env.development             # Dev environment variables
├── .env.production              # Prod environment variables
├── .env.example                 # Template
└── manage.py
```

## Need More Help?

See `ENVIRONMENT_SETUP.md` for detailed documentation.
