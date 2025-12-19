# Complete Fresh cPanel Python App Setup - ELTAN Project
## From Zero to Working Application

**This guide sets up Django on cPanel with web.eltanigeria.org subdomain**

---

## PART 1: PREPARATION & BACKUP

### 1.1 Backup Critical Data

```bash
# SSH into your server
ssh eltanige@s688

# Navigate to home directory
cd /home/eltanige

# Backup database
mysqldump -u eltanige_eltan_user -p eltanige_eltandb > db_backup_$(date +%Y%m%d_%H%M%S).sql

# Backup media files (if any)
tar -czf media_backup_$(date +%Y%m%d_%H%M%S).tar.gz eltanmain/media/

# Verify backups exist
ls -lh *.sql
ls -lh *.tar.gz
```

### 1.2 Note Your Current Configuration

Write down:
- Database name: `eltanige_eltandb`
- Database user: `eltanige_eltan_user`
- Database password: `[your password]`
- Project directory: `/home/eltanige/eltanmain`
- Subdomain: `web.eltanigeria.org`

---

## PART 2: CLEAN UP OLD CONFIGURATION

### 2.1 Delete Python App in cPanel

1. **Log into cPanel**
2. **Go to "Setup Python App"**
3. **Find any existing Python apps**
4. **Click "Destroy" or trash icon**
5. **Confirm deletion**

### 2.2 Clean Up Subdomain Directory

```bash
# Navigate to subdomain directory
cd /home/eltanige/web.eltanigeria.org/

# Remove ALL files except keep the directory
rm -rf * .[^.]* 2>/dev/null

# Verify it's empty
ls -la
# Should only show . and ..
```

### 2.3 Verify Main Project Directory

```bash
cd /home/eltanige/eltanmain

# Verify essential files exist
ls -la passenger_wsgi.py
ls -la manage.py
ls -la .env

# Pull latest code from GitHub
git pull origin main

# Verify static files exist
ls -la static/css/
```

---

## PART 3: CREATE PYTHON APPLICATION IN CPANEL

### 3.1 Navigate to Python App Setup

1. **Log into cPanel**
2. **Search for "Python"**
3. **Click "Setup Python App"**

### 3.2 Create New Application

**Click "Create Application" button**

Fill in the form EXACTLY as shown:

| Field | Value | Notes |
|-------|-------|-------|
| **Python version** | `3.13` | Or latest available (3.11+) |
| **Application root** | `/home/eltanige/eltanmain` | Where your Django code lives |
| **Application URL** | Select `web.eltanigeria.org` from dropdown | Your subdomain |
| **Application startup file** | `passenger_wsgi.py` | Default, don't change |
| **Application entry point** | `application` | Default, don't change |

**IMPORTANT:** Do NOT click Create yet!

### 3.3 Configure Static Files (CRITICAL!)

**Scroll down to "Static files" section**

**Click "+ Add" button**

**First mapping:**
- **URL:** `/static`
- **Path:** `/home/eltanige/eltanmain/staticfiles`

**Click "+ Add" again**

**Second mapping:**
- **URL:** `/media`
- **Path:** `/home/eltanige/eltanmain/media`

### 3.4 Create the Application

**Now click "Create" button**

cPanel will:
- Create virtual environment
- Install initial packages
- Configure Passenger
- Map static files

**Wait for success message**

---

## PART 4: INSTALL DEPENDENCIES

### 4.1 Find Virtual Environment Path

In the Python App interface, you'll see:
```
Command to enter to virtual environment:
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate && cd /home/eltanige/eltanmain
```

**Copy this command!**

### 4.2 SSH and Install Packages

```bash
# SSH into server
ssh eltanige@s688

# Activate virtual environment (use the command from cPanel)
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate && cd /home/eltanige/eltanmain

# Verify Python version
python --version
# Should show: Python 3.13.x

# Upgrade pip
pip install --upgrade pip

# Install base requirements
pip install -r requirements/base.txt

# Install production requirements
pip install -r requirements/production.txt

# Verify critical packages
pip list | grep -i django
pip list | grep -i jazzmin
pip list | grep -i pymysql
pip list | grep -i weasyprint
```

---

## PART 5: CONFIGURE ENVIRONMENT

### 5.1 Verify .env File Exists

```bash
cd /home/eltanige/eltanmain

# Check if .env exists
ls -la .env

# If it exists, verify contents
cat .env
```

### 5.2 Update .env if Needed

```bash
# Edit .env file
nano .env
```

**Ensure these variables are set:**

```bash
# Django Core
SECRET_KEY=your_unique_secret_key_here
DEBUG=False

# Database
DB_NAME=eltanige_eltandb
DB_USER=eltanige_eltan_user
DB_PASSWORD=your_actual_database_password
DB_HOST=localhost
DB_PORT=3306

# Site Configuration
SITE_URL=https://web.eltanigeria.org
ALLOWED_HOSTS=web.eltanigeria.org,www.eltanigeria.org,eltanigeria.org

# Optional (can be empty for now)
PAYSTACK_SECRET_KEY=
PAYSTACK_PUBLIC_KEY=
USER_EMAIL=
USER_PASSWORD=
```

**Save:** Ctrl+X, Y, Enter

**Set permissions:**
```bash
chmod 600 .env
```

---

## PART 6: PREPARE DIRECTORIES

### 6.1 Create Required Directories

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

## PART 7: DATABASE SETUP

### 7.1 Run Migrations

```bash
cd /home/eltanige/eltanmain
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate

# Check for issues
python manage.py check --settings=eltanweb.settings.production

# Run migrations
python manage.py migrate --settings=eltanweb.settings.production
```

### 7.2 Create Superuser (if needed)

```bash
python manage.py createsuperuser --settings=eltanweb.settings.production
```

---

## PART 8: COLLECT STATIC FILES

### 8.1 Run collectstatic

```bash
cd /home/eltanige/eltanmain
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate

# Clear old files
rm -rf staticfiles/*

# Collect static files
python manage.py collectstatic --settings=eltanweb.settings.production --noinput

# Verify files were collected
echo "Total static files:"
find staticfiles -type f | wc -l

# Check CSS files specifically
ls -la staticfiles/css/
```

**Expected output:** Should see hundreds of files including:
- `staticfiles/css/style.css`
- `staticfiles/css/bootstrap.min.css`
- `staticfiles/css/landing-modern.css`
- etc.

### 8.2 Set Permissions

```bash
chmod -R 755 staticfiles/
```

---

## PART 9: PASSENGER CONFIGURATION

### 9.1 Verify passenger_wsgi.py

```bash
cd /home/eltanige/eltanmain
cat passenger_wsgi.py
```

**Should contain:**
```python
import os
import sys

# Add your project directory to the sys.path
project_home = '/home/eltanige/eltanmain'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eltanweb.settings.production')

# Import the WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**If different or missing, create it:**
```bash
nano passenger_wsgi.py
# Paste the content above
# Save: Ctrl+X, Y, Enter
```

### 9.2 NO .htaccess Needed in Project Root

**IMPORTANT:** For cPanel Python apps, you do NOT need .htaccess in the project root (`/home/eltanige/eltanmain/`).

```bash
cd /home/eltanige/eltanmain

# If .htaccess exists, rename it
mv .htaccess .htaccess.not_needed 2>/dev/null
```

**Why?** The Python App configuration in cPanel handles everything automatically.

---

## PART 10: SUBDOMAIN DIRECTORY

### 10.1 Leave Subdomain Directory Empty

```bash
cd /home/eltanige/web.eltanigeria.org/

# Should be empty
ls -la
# Should only show . and ..
```

**IMPORTANT:** Do NOT put anything in this directory. cPanel's Python App handles everything.

### 10.2 NO .htaccess Needed in Subdomain

The subdomain directory should be completely empty. cPanel manages it automatically.

---

## PART 11: RESTART APPLICATION

### 11.1 Restart via Command Line

```bash
cd /home/eltanige/eltanmain
touch tmp/restart.txt
```

### 11.2 OR Restart via cPanel

1. **Go to "Setup Python App"**
2. **Find your app**
3. **Click "Restart" button**

---

## PART 12: TESTING

### 12.1 Test in Browser

**Open a new private/incognito window** (to avoid cache)

**Test these URLs:**

1. **Homepage:**
   - URL: `https://web.eltanigeria.org/`
   - Expected: Page loads with CSS styling

2. **Static CSS:**
   - URL: `https://web.eltanigeria.org/static/css/style.css`
   - Expected: CSS file displays

3. **Admin Panel:**
   - URL: `https://web.eltanigeria.org/admin/`
   - Expected: Login page with styling

### 12.2 Check Browser Developer Tools

**Press F12 to open Developer Tools**

**Go to "Network" tab**

**Refresh the page**

**Check:**
- All CSS files: Status **200 OK** (green)
- All JS files: Status **200 OK** (green)
- All images: Status **200 OK** (green)
- Main page: Status **200 OK** (green)

**No red (failed) requests!**

### 12.3 Test Login

1. Go to `https://web.eltanigeria.org/admin/`
2. Login with superuser credentials
3. Verify admin interface works

---

## PART 13: VERIFICATION CHECKLIST

After setup, verify:

- [ ] Python app shows "Running" in cPanel
- [ ] Homepage loads at `https://web.eltanigeria.org/`
- [ ] Homepage has CSS styling
- [ ] Admin panel loads at `https://web.eltanigeria.org/admin/`
- [ ] Admin panel has styling
- [ ] Static files load (check Network tab in browser)
- [ ] No 404 errors for CSS/JS files
- [ ] Can login to admin successfully
- [ ] Database connection works
- [ ] No errors in logs

---

## TROUBLESHOOTING

### Issue: "No module named 'django'"

**Solution:**
```bash
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate
pip install -r requirements/production.txt
touch tmp/restart.txt
```

### Issue: Homepage shows 404

**Check:**
1. Python app is "Running" in cPanel
2. Application URL is set to `web.eltanigeria.org`
3. passenger_wsgi.py exists in project root
4. Restart app: `touch tmp/restart.txt`

### Issue: Static files show 404

**Check:**
1. Static file mappings exist in cPanel Python App
2. collectstatic was run successfully
3. staticfiles/css/ directory has files
4. Restart app

### Issue: Database connection error

**Check:**
1. .env file has correct database credentials
2. MySQL database exists
3. Database user has permissions
4. Test: `mysql -u eltanige_eltan_user -p eltanige_eltandb -e "SELECT 1;"`

### Issue: 500 Internal Server Error

**Check logs:**
```bash
tail -50 /home/eltanige/eltanmain/logs/error.log
tail -50 /home/eltanige/eltanmain/logs/production.log
```

---

## IMPORTANT NOTES

### What Goes Where:

| Location | What Goes There | Why |
|----------|----------------|-----|
| `/home/eltanige/eltanmain/` | Django project, passenger_wsgi.py, .env | Your application code |
| `/home/eltanige/eltanmain/staticfiles/` | Collected static files | Created by collectstatic |
| `/home/eltanige/eltanmain/media/` | User uploads | Django MEDIA_ROOT |
| `/home/eltanige/web.eltanigeria.org/` | **NOTHING** | Managed by cPanel automatically |
| `/home/eltanige/virtualenv/eltanmain/3.13/` | Python packages | Created by cPanel |

### Key Points:

1. **NO .htaccess needed** - cPanel Python App handles it
2. **NO files in subdomain directory** - cPanel manages it
3. **Static file mappings** in cPanel are critical
4. **passenger_wsgi.py** must be in project root
5. **Always activate virtualenv** before Django commands

---

## MAINTENANCE COMMANDS

### Update code from Git:
```bash
cd /home/eltanige/eltanmain
git pull origin main
source /home/eltanige/virtualenv/eltanmain/3.13/bin/activate
pip install -r requirements/production.txt
python manage.py migrate --settings=eltanweb.settings.production
python manage.py collectstatic --settings=eltanweb.settings.production --noinput
touch tmp/restart.txt
```

### View logs:
```bash
tail -f /home/eltanige/eltanmain/logs/production.log
tail -f /home/eltanige/eltanmain/logs/error.log
```

### Restart app:
```bash
touch /home/eltanige/eltanmain/tmp/restart.txt
```

---

## SUCCESS CRITERIA

✅ **You'll know it's working when:**

1. Visit `https://web.eltanigeria.org/`
2. Page loads with full CSS styling
3. Navigation menu looks correct
4. Images and fonts load
5. Admin panel at `/admin/` works with styling
6. No 404 errors in browser console
7. Everything looks professional and polished

---

**Setup Complete!** 🎉

Your Django application is now properly configured on cPanel with web.eltanigeria.org subdomain and full static file support.
