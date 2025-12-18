# cPanel Python App Setup Guide - ELTAN Project

**Complete guide for setting up Django on cPanel with proper static file serving**

---

## Prerequisites

- cPanel account with Python app support
- SSH access to server
- Git installed on server
- MySQL database created in cPanel

---

## Step 1: Create Python Application in cPanel

1. **Log into cPanel**
2. **Go to "Setup Python App"**
3. **Click "Create Application"**

### Application Configuration:

| Setting | Value |
|---------|-------|
| **Python Version** | 3.13 (or latest available) |
| **Application Root** | `/home/eltanige/eltanmain` |
| **Application URL** | `web.eltanigeria.org` (or your domain) |
| **Application Startup File** | `passenger_wsgi.py` |
| **Application Entry Point** | `application` |

4. **Click "Create"**

---

## Step 2: Configure Static and Media File Mappings

**IMPORTANT:** This must be done in the Python App configuration!

In the Python App interface, scroll to **"Static files"** section:

### Add Static Files Mapping:
- **URL:** `/static`
- **Path:** `/home/eltanige/eltanmain/staticfiles`

### Add Media Files Mapping:
- **URL:** `/media`
- **Path:** `/home/eltanige/eltanmain/media`

**Click "Save" or "Update"**

---

## Step 3: Clone Repository and Setup Project

### Via SSH:

```bash
# Navigate to home directory
cd /home/eltanige

# If eltanmain already exists, rename it
mv eltanmain eltanmain.old 2>/dev/null

# Clone from GitHub
git clone https://github.com/ojsys/eltan-main.git eltanmain

# Navigate to project
cd eltanmain

# Verify files
ls -la
```

---

## Step 4: Activate Virtual Environment

cPanel creates a virtual environment automatically. Find and activate it:

```bash
# Find the virtualenv path (check in cPanel Python App settings)
# Usually something like: /home/eltanige/virtualenv/eltanmain/3.13

# Activate it
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate

# Verify Python version
python --version  # Should show Python 3.13.x

# Verify pip location
which pip  # Should point to virtualenv
```

---

## Step 5: Install Dependencies

```bash
cd /home/eltanige/eltanmain
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate

# Install production requirements
pip install --upgrade pip
pip install -r requirements/base.txt
pip install -r requirements/production.txt

# Verify critical packages are installed
pip list | grep -i django
pip list | grep -i jazzmin
pip list | grep -i pymysql
pip list | grep -i weasyprint
```

---

## Step 6: Create and Configure .env File

```bash
cd /home/eltanige/eltanmain
nano .env
```

**Add these variables** (replace with your actual values):

```bash
# Django Settings
SECRET_KEY=your_unique_secret_key_here
DEBUG=False

# Database Configuration
DB_NAME=eltanige_eltandb
DB_USER=eltanige_eltan_user
DB_PASSWORD=your_actual_database_password
DB_HOST=localhost
DB_PORT=3306

# Paystack Configuration (optional - can be empty for now)
PAYSTACK_SECRET_KEY=your_paystack_secret_key
PAYSTACK_PUBLIC_KEY=your_paystack_public_key

# Email Configuration (optional - can be empty for now)
USER_EMAIL=eltanigeria001@gmail.com
USER_PASSWORD=your_gmail_app_password

# Site Configuration
SITE_URL=https://web.eltanigeria.org
ALLOWED_HOSTS=web.eltanigeria.org,www.eltanigeria.org,eltanigeria.org
```

**Save and exit** (Ctrl+X, Y, Enter)

**Set proper permissions:**
```bash
chmod 600 .env
```

---

## Step 7: Create Required Directories

```bash
cd /home/eltanige/eltanmain

# Create directories
mkdir -p logs
mkdir -p media
mkdir -p staticfiles
mkdir -p tmp

# Set permissions
chmod 755 logs
chmod 755 media
chmod 755 staticfiles
chmod 755 tmp
```

---

## Step 8: Verify passenger_wsgi.py

Check that the file exists and has correct content:

```bash
cd /home/eltanige/eltanmain
cat passenger_wsgi.py
```

**It should contain:**
```python
import os
import sys

# Add your project directory to the sys.path
project_home = '/home/eltanige/eltanmain'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set the settings module
# python-decouple will automatically read from .env file
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eltanweb.settings.production')

# Import the WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**If file doesn't exist or is wrong, create/fix it:**
```bash
nano passenger_wsgi.py
# Paste the content above, save and exit
```

---

## Step 9: Run Database Migrations

```bash
cd /home/eltanige/eltanmain
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate

# Check for any issues first
python manage.py check --deploy --settings=eltanweb.settings.production

# Run migrations
python manage.py migrate --settings=eltanweb.settings.production

# Create superuser (for admin access)
python manage.py createsuperuser --settings=eltanweb.settings.production
```

---

## Step 10: Collect Static Files

```bash
cd /home/eltanige/eltanmain
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate

# Collect all static files
python manage.py collectstatic --settings=eltanweb.settings.production --noinput

# Verify files were collected
ls -la staticfiles/
echo "Total static files:"
find staticfiles -type f | wc -l

# Check custom CSS files
ls -la staticfiles/css/

# Set permissions
chmod -R 755 staticfiles/
```

---

## Step 11: Restart the Application

```bash
cd /home/eltanige/eltanmain
touch tmp/restart.txt
```

**Or restart via cPanel:**
1. Go to **Setup Python App**
2. Find your app
3. Click **"Restart"** button

---

## Step 12: Test the Application

### In Browser:

1. **Visit:** `https://web.eltanigeria.org`
2. **Expected:** Site loads with CSS/styling
3. **Test admin:** `https://web.eltanigeria.org/admin`

### Check Static Files:

1. Open **Browser Developer Tools** (F12)
2. Go to **Network** tab
3. Refresh page
4. **Verify:** All `/static/css/*.css` files return **200 OK** (green)

### If Static Files Still Don't Load:

```bash
# Verify static file mappings in cPanel
# Go to: Setup Python App → Edit App → Check "Static files" section

# Should have:
# URL: /static  →  Path: /home/eltanige/eltanmain/staticfiles
# URL: /media   →  Path: /home/eltanige/eltanmain/media
```

---

## Step 13: Restore Database Backup (if needed)

If you have an existing database backup:

```bash
# Restore from backup
mysql -u eltanige_eltan_user -p eltanige_eltandb < /home/eltanige/eltandb_backup_YYYYMMDD_HHMMSS.sql

# Verify
mysql -u eltanige_eltan_user -p eltanige_eltandb -e "SELECT COUNT(*) FROM account_customuser;"
```

---

## Troubleshooting Common Issues

### Issue 1: "No module named 'django'"

**Solution:**
```bash
# Make sure virtualenv is activated
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate

# Reinstall dependencies
pip install -r requirements/production.txt
```

### Issue 2: Static Files Not Loading (404)

**Solution:**
1. Verify static file mappings in cPanel Python App settings
2. Check collectstatic ran successfully: `ls staticfiles/css/`
3. Check file permissions: `chmod -R 755 staticfiles/`
4. Restart app: `touch tmp/restart.txt`

### Issue 3: Database Connection Error

**Solution:**
```bash
# Verify .env file has correct credentials
cat .env | grep DB_

# Test database connection
mysql -u eltanige_eltan_user -p eltanige_eltandb -e "SELECT 1;"
```

### Issue 4: "Settings object has no attribute 'ROOT_URLCONF'"

**Solution:**
```bash
# Check .env file exists and is readable
ls -la .env
cat .env | head -5

# Verify DJANGO_SETTINGS_MODULE in passenger_wsgi.py
grep DJANGO_SETTINGS_MODULE passenger_wsgi.py
```

### Issue 5: 500 Internal Server Error

**Solution:**
```bash
# Check error logs
tail -50 logs/error.log
tail -50 logs/production.log

# Check cPanel error logs (location may vary)
tail -50 /home/eltanige/logs/web.eltanigeria.org-error_log
```

---

## Maintenance Commands

### Update Code from GitHub:
```bash
cd /home/eltanige/eltanmain
git pull origin main
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate
pip install -r requirements/production.txt
python manage.py migrate --settings=eltanweb.settings.production
python manage.py collectstatic --settings=eltanweb.settings.production --noinput
touch tmp/restart.txt
```

### View Logs:
```bash
# Django logs
tail -f /home/eltanige/eltanmain/logs/production.log
tail -f /home/eltanige/eltanmain/logs/error.log

# cPanel logs
tail -f /home/eltanige/logs/web.eltanigeria.org-error_log
```

### Backup Database:
```bash
cd /home/eltanige
mysqldump -u eltanige_eltan_user -p eltanige_eltandb > backup_$(date +%Y%m%d_%H%M%S).sql
```

---

## Security Checklist

- [ ] `DEBUG=False` in .env
- [ ] `.env` file has `chmod 600` permissions
- [ ] `SECRET_KEY` is unique and not in git
- [ ] Database password is strong
- [ ] ALLOWED_HOSTS configured correctly
- [ ] SSL certificate is active (HTTPS)
- [ ] Regular database backups scheduled

---

## Important Notes

1. **Never commit `.env` file to git** - it contains secrets
2. **Always activate virtualenv** before running Django commands
3. **Run `collectstatic`** after any static file changes
4. **Restart app** (`touch tmp/restart.txt`) after code/settings changes
5. **Keep regular database backups**

---

## Quick Reference

| Task | Command |
|------|---------|
| Activate virtualenv | `source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate` |
| Run migrations | `python manage.py migrate --settings=eltanweb.settings.production` |
| Collect static | `python manage.py collectstatic --settings=eltanweb.settings.production --noinput` |
| Restart app | `touch /home/eltanige/eltanmain/tmp/restart.txt` |
| View logs | `tail -f logs/production.log` |
| Database shell | `python manage.py dbshell --settings=eltanweb.settings.production` |

---

**Setup Complete!** Your Django application should now be running correctly on cPanel with proper static file serving.

If you encounter any issues, refer to the Troubleshooting section or check the logs.
