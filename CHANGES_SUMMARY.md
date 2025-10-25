# Environment Separation - Changes Summary

## Overview

The ELTAN project has been restructured to properly separate development and production environments. This ensures better security, easier maintenance, and clearer deployment processes.

## What Changed

### 1. Settings Restructure

**Before**: Single `eltanweb/settings.py` file with try/except logic

**After**: Modular settings package
- `eltanweb/settings/base.py` - Common settings
- `eltanweb/settings/development.py` - Development-specific settings
- `eltanweb/settings/production.py` - Production-specific settings
- `eltanweb/settings/__init__.py` - Package initialization

### 2. Environment Configuration Files

**Created**:
- `.env.development` - Development environment variables (SQLite, test keys)
- `.env.production` - Production environment variables (MySQL, live keys)
- `.env.example` - Template showing all required variables

**Modified**:
- `.env` - Should now be copied from either `.env.development` or `.env.production`

### 3. Requirements Files

**Before**: Single `requirements.txt` with all dependencies

**After**: Organized requirements structure
- `requirements/base.txt` - Common dependencies
- `requirements/development.txt` - Dev-only packages (livereload, etc.)
- `requirements/production.txt` - Prod-only packages (PyMySQL, etc.)
- `requirements.txt` - Points to production.txt for backward compatibility

### 4. Application Entry Points

**Updated**:
- `manage.py` - Now checks `ELTAN_ENV` variable (defaults to development)
- `eltanweb/wsgi.py` - Now checks `ELTAN_ENV` variable (defaults to production)
- `eltanweb/asgi.py` - Now checks `ELTAN_ENV` variable (defaults to production)

### 5. Documentation

**Created**:
- `ENVIRONMENT_SETUP.md` - Comprehensive environment setup guide
- `QUICK_START_ENVIRONMENTS.md` - Quick reference for common tasks
- `CHANGES_SUMMARY.md` - This file
- `.gitignore` - Proper gitignore for Django projects

## Key Improvements

### Security Enhancements (Production)

1. **Debug Mode**: Automatically disabled in production
2. **SSL Enforcement**: HTTPS redirect enabled
3. **Secure Cookies**: Session and CSRF cookies use secure flag
4. **HSTS Headers**: HTTP Strict Transport Security enabled
5. **Restricted Hosts**: Only allows configured domains
6. **Separate Logging**: Error-focused logging in production

### Development Experience

1. **SQLite Auto-Config**: No database setup needed
2. **Console Email**: Emails printed to terminal
3. **Live Reload**: Auto-refresh on code changes
4. **Debug Mode**: Detailed error pages
5. **Verbose Logging**: Full request/response logging

### Database Configuration

**Development**:
- Uses SQLite automatically
- Database file: `db.sqlite3`
- No configuration needed

**Production**:
- Uses MySQL from `.env` configuration
- Requires: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
- Connection pooling enabled (CONN_MAX_AGE)

### Payment Gateway Configuration

**Development**:
- Uses test Paystack keys
- Payments won't charge real money
- Test keys in code for easy access

**Production**:
- Uses live Paystack keys from `.env`
- Real payment processing
- Keys kept secure in environment variables

## Migration Guide

### For Developers (Local Development)

1. **Update environment**:
   ```bash
   cp .env.development .env
   export ELTAN_ENV=development
   ```

2. **Reinstall dependencies**:
   ```bash
   pip install -r requirements/development.txt
   ```

3. **Run as usual**:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

### For Production Deployment

1. **Update environment**:
   ```bash
   cp .env.production .env
   nano .env  # Update with actual credentials
   export ELTAN_ENV=production
   ```

2. **Reinstall dependencies**:
   ```bash
   pip install -r requirements/production.txt
   ```

3. **Deploy**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   # Restart web server
   ```

## Backward Compatibility

The old `settings.py` file has been replaced, but the project maintains compatibility:

- `requirements.txt` still works (points to production requirements)
- Default behavior favors safety (production settings for WSGI)
- Existing `.env` file continues to work

## Environment Variable Control

You can control the environment in three ways:

1. **ELTAN_ENV variable** (recommended):
   ```bash
   export ELTAN_ENV=development  # or production
   ```

2. **DJANGO_SETTINGS_MODULE**:
   ```bash
   export DJANGO_SETTINGS_MODULE=eltanweb.settings.development
   ```

3. **Command line argument**:
   ```bash
   python manage.py runserver --settings=eltanweb.settings.development
   ```

## File Structure Changes

### New Files
```
eltanweb/settings/
├── __init__.py
├── base.py
├── development.py
└── production.py

requirements/
├── base.txt
├── development.txt
└── production.txt

.env.development
.env.production
.env.example
.gitignore
ENVIRONMENT_SETUP.md
QUICK_START_ENVIRONMENTS.md
CHANGES_SUMMARY.md
```

### Modified Files
```
manage.py              # Updated to use ELTAN_ENV
eltanweb/wsgi.py      # Updated to use ELTAN_ENV
eltanweb/asgi.py      # Updated to use ELTAN_ENV
requirements.txt       # Now points to requirements/production.txt
```

### Deprecated Files
```
eltanweb/settings.py  # Replaced by settings/ package
```

## Testing the Setup

### Test Development Environment

```bash
export ELTAN_ENV=development
python manage.py check
python manage.py migrate
python manage.py runserver
```

Expected behavior:
- Uses SQLite database
- Debug mode enabled
- Emails to console
- Accessible at http://localhost:8000

### Test Production Environment

```bash
export ELTAN_ENV=production
python manage.py check --deploy
```

Expected behavior:
- Checks for MySQL connection
- Debug mode disabled
- Security checks pass
- Validates production configuration

## Common Issues and Solutions

### Issue: "No module named 'eltanweb.settings'"

**Solution**: Update `DJANGO_SETTINGS_MODULE`:
```bash
export DJANGO_SETTINGS_MODULE=eltanweb.settings.development
```

### Issue: "Database configuration error"

**Solution**: Check your `.env` file:
```bash
cat .env | grep DB_
```

### Issue: "Static files not found"

**Solution**: Collect static files:
```bash
python manage.py collectstatic --noinput
```

## Next Steps

1. **Review** the new settings files to understand the configuration
2. **Test** both development and production environments locally
3. **Update** deployment scripts if any
4. **Train** team members on new environment setup
5. **Deploy** to production following the migration guide

## Support

For questions or issues:
- Review `ENVIRONMENT_SETUP.md` for detailed setup
- Check `QUICK_START_ENVIRONMENTS.md` for quick commands
- Contact the development team

---

**Date**: 2024
**Version**: 1.0
**Author**: Environment Separation Update
