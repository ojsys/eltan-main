# ELTAN Environment Configuration Guide

This guide explains how to set up and run the ELTAN project in different environments (development vs production).

## Overview

The ELTAN project now uses a **modular settings structure** that separates configuration for development and production environments. This ensures:

- **Development**: Uses SQLite database, debug mode enabled, test payment keys
- **Production**: Uses MySQL database on cPanel, debug mode disabled, live payment keys, enhanced security

## Project Structure

```
eltanweb/
├── settings/
│   ├── __init__.py           # Settings package initialization
│   ├── base.py               # Common settings for all environments
│   ├── development.py        # Development-specific settings
│   └── production.py         # Production-specific settings
├── wsgi.py                   # WSGI configuration (production default)
├── asgi.py                   # ASGI configuration (production default)
└── urls.py                   # URL routing
```

## Environment Variables

The project uses environment variables to manage sensitive configuration. These are stored in `.env` files.

### Available .env Files

| File | Purpose |
|------|---------|
| `.env.example` | Template file showing all required variables |
| `.env.development` | Development environment variables |
| `.env.production` | Production environment variables |
| `.env` | Active environment file (gitignored) |

### Setting Up Environment Variables

1. **For Development**:
   ```bash
   cp .env.development .env
   ```

2. **For Production**:
   ```bash
   cp .env.production .env
   ```

3. **Review and Update**: Edit `.env` file with your actual credentials

## Running the Project

### Development Mode

Development mode uses:
- SQLite database (no MySQL needed)
- Django debug toolbar
- Console email backend (emails printed to console)
- Live reload for auto-refresh
- Test Paystack keys

**Steps**:

1. Set up virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements/development.txt
   ```

3. Copy development environment variables:
   ```bash
   cp .env.development .env
   ```

4. Set environment to development:
   ```bash
   export ELTAN_ENV=development  # On Windows: set ELTAN_ENV=development
   ```

5. Run migrations:
   ```bash
   python manage.py migrate
   ```

6. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Run development server:
   ```bash
   python manage.py runserver
   ```

8. Access the application:
   - Website: http://localhost:8000
   - Admin: http://localhost:8000/admin

### Production Mode

Production mode uses:
- MySQL database on cPanel
- SMTP email backend
- Live Paystack keys
- Enhanced security settings
- SSL enforcement

**Steps**:

1. Set up virtual environment on server:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install production dependencies:
   ```bash
   pip install -r requirements/production.txt
   ```

3. Copy production environment variables:
   ```bash
   cp .env.production .env
   ```

4. **IMPORTANT**: Edit `.env` and update:
   - `SECRET_KEY` - Generate a new secure key
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD` - Your cPanel MySQL credentials
   - `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY` - Your live Paystack keys
   - `USER_EMAIL`, `USER_PASSWORD` - Your SMTP credentials

5. Set environment to production:
   ```bash
   export ELTAN_ENV=production
   ```

6. Run migrations:
   ```bash
   python manage.py migrate
   ```

7. Collect static files:
   ```bash
   python manage.py collectstatic --noinput
   ```

8. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```

9. Configure your web server (Apache/Nginx) to use the WSGI application

## Environment Settings Comparison

| Setting | Development | Production |
|---------|-------------|------------|
| **DEBUG** | True | False |
| **ALLOWED_HOSTS** | ['*'] | ['eltanigeria.org', 'www.eltanigeria.org'] |
| **Database** | SQLite | MySQL |
| **Email Backend** | Console | SMTP |
| **Paystack Keys** | Test keys | Live keys |
| **SSL Redirect** | Disabled | Enabled |
| **Secure Cookies** | Disabled | Enabled |
| **Logging Level** | DEBUG | WARNING/ERROR |

## Environment Variable Reference

### Required Variables

```env
# Django Security
SECRET_KEY=your-secret-key-here

# Paystack Payment Gateway
PAYSTACK_SECRET_KEY=sk_test_or_sk_live_...
PAYSTACK_PUBLIC_KEY=pk_test_or_pk_live_...

# Email Configuration
USER_EMAIL=your-email@gmail.com
USER_PASSWORD=your-app-specific-password
```

### Production-Only Variables

```env
# MySQL Database (Production)
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=3306
```

## Switching Between Environments

### Method 1: Environment Variable

```bash
# Development
export ELTAN_ENV=development
python manage.py runserver

# Production
export ELTAN_ENV=production
python manage.py runserver
```

### Method 2: Django Settings Module

```bash
# Development
python manage.py runserver --settings=eltanweb.settings.development

# Production
python manage.py runserver --settings=eltanweb.settings.production
```

### Method 3: Update .env File

Switch between `.env.development` and `.env.production`:

```bash
# For development
cp .env.development .env

# For production
cp .env.production .env
```

## cPanel Deployment

For deploying to cPanel with Passenger:

1. **Upload files** to your cPanel account

2. **Create MySQL database** in cPanel:
   - Go to MySQL Databases
   - Create database and user
   - Grant all privileges
   - Update `.env` with credentials

3. **Set up virtual environment**:
   ```bash
   cd ~/public_html/eltanigeria.org
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements/production.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.production .env
   # Edit .env with your actual credentials
   export ELTAN_ENV=production
   ```

5. **Run migrations**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic
   ```

6. **Configure Passenger**:
   - In cPanel, go to "Setup Python App"
   - Set Application Root to your project directory
   - Set Application URL to your domain
   - Set Python version
   - Application Startup File: `passenger_wsgi.py`
   - Application Entry Point: `application`

7. **Restart application** in cPanel Python App interface

## Troubleshooting

### Issue: "Settings module not found"

**Solution**: Ensure `ELTAN_ENV` is set correctly:
```bash
export ELTAN_ENV=development  # or production
```

### Issue: Database connection error in production

**Solution**: Check `.env` file has correct MySQL credentials:
```bash
cat .env | grep DB_
```

### Issue: Static files not loading

**Solution**: Run collectstatic:
```bash
python manage.py collectstatic --noinput
```

### Issue: "DEBUG may not be set to True in production"

**Solution**: Verify `ELTAN_ENV=production` is set and `DEBUG=False` in `settings/production.py`

### Issue: Email not sending in development

**Solution**: This is expected. Development uses console backend. Check terminal output for email content.

## Security Checklist for Production

Before deploying to production, ensure:

- [ ] `DEBUG = False` in production settings
- [ ] Generated new `SECRET_KEY` (not the default one)
- [ ] Using live Paystack keys, not test keys
- [ ] MySQL database credentials are correct
- [ ] `ALLOWED_HOSTS` contains only your actual domain(s)
- [ ] `.env` file is not in version control (check `.gitignore`)
- [ ] SSL certificate is installed and `SECURE_SSL_REDIRECT = True`
- [ ] Database backups are configured
- [ ] Log files directory exists and is writable (`logs/`)

## Additional Resources

- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Paystack Documentation](https://paystack.com/docs)
- [cPanel Python App Documentation](https://docs.cpanel.net/ea4/passenger/)

## Support

For issues or questions:
- Check existing documentation in `/docs`
- Review Django logs in `logs/` directory
- Contact the development team
