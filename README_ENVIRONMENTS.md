# ELTAN Project - Environment Management

Welcome to the ELTAN (Emerging Leaders Training and Nurturing) project! This README explains the new environment separation structure.

## 🚀 Quick Start

### For Development (First Time)

```bash
# 1. Use the helper script (Mac/Linux)
source set_env.sh development

# Or on Windows
set_env.bat development

# 2. Install dependencies
pip install -r requirements/development.txt

# 3. Run migrations
python manage.py migrate

# 4. Create admin user
python manage.py createsuperuser

# 5. Start server
python manage.py runserver
```

Visit: http://localhost:8000

### For Production Deployment

```bash
# 1. Use the helper script
source set_env.sh production  # or set_env.bat production on Windows

# 2. EDIT .env file with your credentials
nano .env

# 3. Install dependencies
pip install -r requirements/production.txt

# 4. Run migrations
python manage.py migrate

# 5. Collect static files
python manage.py collectstatic --noinput

# 6. Restart your web server
```

## 📁 Project Structure

```
eltan2/
├── eltanweb/                    # Main project package
│   ├── settings/                # Settings package
│   │   ├── base.py             # Common settings
│   │   ├── development.py      # Development settings
│   │   └── production.py       # Production settings
│   ├── wsgi.py                 # WSGI entry point
│   ├── asgi.py                 # ASGI entry point
│   └── urls.py                 # URL configuration
│
├── requirements/                # Dependencies
│   ├── base.txt                # Common packages
│   ├── development.txt         # Dev packages
│   └── production.txt          # Prod packages
│
├── account/                     # User authentication app
├── membership/                  # Membership management
├── payments/                    # Payment processing
├── core/                        # Core CMS functionality
├── mainapp/                     # Main application
│
├── static/                      # Static files (CSS, JS, images)
├── media/                       # User uploads
├── templates/                   # HTML templates
├── logs/                        # Application logs
│
├── .env.development            # Dev environment vars
├── .env.production             # Prod environment vars
├── .env.example                # Template
├── .env                        # Active (gitignored)
│
├── set_env.sh                  # Environment switcher (Mac/Linux)
├── set_env.bat                 # Environment switcher (Windows)
│
├── manage.py                   # Django management
├── requirements.txt            # Main requirements (→ production)
└── db.sqlite3                  # SQLite database (dev)
```

## 🔧 Environment Configuration

### Development Environment

**Characteristics:**
- ✅ SQLite database (no setup needed)
- ✅ Debug mode enabled (detailed errors)
- ✅ Console email backend (see emails in terminal)
- ✅ Test Paystack keys (no real charges)
- ✅ Live reload enabled
- ✅ Relaxed security settings
- ✅ Verbose logging

**When to use:**
- Local development
- Testing new features
- Learning Django
- Running tests

### Production Environment

**Characteristics:**
- ✅ MySQL database on cPanel
- ✅ Debug mode disabled
- ✅ SMTP email backend (real emails)
- ✅ Live Paystack keys (real payments)
- ✅ SSL/HTTPS enforcement
- ✅ Secure cookies
- ✅ Error-only logging
- ✅ Static file optimization

**When to use:**
- Live website (eltanigeria.org)
- Staging server
- Production deployment
- Real user traffic

## 🎯 Environment Variables

### Required Variables (All Environments)

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `PAYSTACK_SECRET_KEY` | Paystack API key | `sk_test_...` or `sk_live_...` |
| `PAYSTACK_PUBLIC_KEY` | Paystack public key | `pk_test_...` or `pk_live_...` |
| `USER_EMAIL` | SMTP email address | `your@email.com` |
| `USER_PASSWORD` | SMTP app password | `your-app-password` |

### Production-Only Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_NAME` | MySQL database name | `eltanige_eltandb` |
| `DB_USER` | MySQL username | `eltanige_eltan_user` |
| `DB_PASSWORD` | MySQL password | `your-password` |
| `DB_HOST` | MySQL host | `localhost` |
| `DB_PORT` | MySQL port | `3306` |

## 🔄 Switching Environments

### Method 1: Helper Scripts (Recommended)

**Mac/Linux:**
```bash
source set_env.sh development  # For development
source set_env.sh production   # For production
```

**Windows:**
```cmd
set_env.bat development  # For development
set_env.bat production   # For production
```

### Method 2: Manual Environment Variable

```bash
# Development
export ELTAN_ENV=development

# Production
export ELTAN_ENV=production
```

### Method 3: Django Settings Module

```bash
python manage.py runserver --settings=eltanweb.settings.development
python manage.py runserver --settings=eltanweb.settings.production
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `QUICK_START_ENVIRONMENTS.md` | Quick reference for common commands |
| `ENVIRONMENT_SETUP.md` | Comprehensive setup guide |
| `CHANGES_SUMMARY.md` | Summary of environment separation changes |
| `README_ENVIRONMENTS.md` | This file |

## 🛠️ Common Commands

### Development

```bash
# Start development server
python manage.py runserver

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Django shell
python manage.py shell

# Run tests
python manage.py test
```

### Production

```bash
# Check deployment settings
python manage.py check --deploy

# Collect static files
python manage.py collectstatic --noinput

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

## 🔒 Security Checklist (Production)

Before deploying to production:

- [ ] `DEBUG = False` in production settings
- [ ] Generated new secure `SECRET_KEY`
- [ ] Using live Paystack keys (not test)
- [ ] MySQL credentials are correct in `.env`
- [ ] `.env` file is NOT in version control
- [ ] `ALLOWED_HOSTS` has only your domain
- [ ] SSL certificate is installed
- [ ] Database backups configured
- [ ] `logs/` directory exists and is writable
- [ ] Static files collected: `python manage.py collectstatic`

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'eltanweb.settings'"

**Solution:**
```bash
export ELTAN_ENV=development  # or production
python manage.py runserver
```

### Database connection error (Production)

**Solution:** Check your `.env` file:
```bash
cat .env | grep DB_
# Verify all DB_* variables are set correctly
```

### Static files not loading

**Solution:**
```bash
python manage.py collectstatic --noinput
```

### Email not sending (Development)

**Expected behavior** - Development uses console backend. Check your terminal for email output.

### Payment not processing (Development)

**Expected behavior** - Development uses test Paystack keys. Use test card numbers from [Paystack docs](https://paystack.com/docs/payments/test-payments).

## 🚢 Deployment to cPanel

1. **Upload files** to cPanel via FTP/Git

2. **Create virtual environment:**
   ```bash
   cd ~/public_html/eltanigeria.org
   python -m venv venv
   source venv/bin/activate
   ```

3. **Set production environment:**
   ```bash
   source set_env.sh production
   nano .env  # Update with actual credentials
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements/production.txt
   ```

5. **Create MySQL database in cPanel:**
   - Go to MySQL Databases
   - Create database and user
   - Update `.env` with credentials

6. **Run Django setup:**
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```

7. **Configure Passenger in cPanel:**
   - Application Root: `/home/user/public_html/eltanigeria.org`
   - Application URL: Your domain
   - Python version: 3.12+
   - Startup file: `passenger_wsgi.py`

8. **Restart application** in cPanel interface

## 🔗 Useful Links

- [Django Documentation](https://docs.djangoproject.com/)
- [Paystack API Docs](https://paystack.com/docs)
- [cPanel Python Apps](https://docs.cpanel.net/ea4/passenger/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)

## 📝 Key Features

- **Membership Management**: Register and manage ELTAN members
- **Payment Processing**: Online payments via Paystack
- **Custom User Model**: Email-based authentication
- **CMS Functionality**: Manage site content and settings
- **Admin Dashboard**: Comprehensive admin interface
- **Email Notifications**: Automated email communications

## 🤝 Contributing

When contributing to this project:

1. Always work in **development environment**
2. Never commit `.env` files
3. Test thoroughly before deploying
4. Update documentation if needed
5. Follow Django best practices

## 📧 Support

For issues or questions:
- Review documentation in `/docs`
- Check logs in `logs/` directory
- Contact the development team

---

**Project**: ELTAN (Emerging Leaders Training and Nurturing)
**Framework**: Django 5.0.4
**Database**: SQLite (Dev) / MySQL (Prod)
**Payment Gateway**: Paystack
**Hosting**: cPanel with Passenger

**Last Updated**: 2024
