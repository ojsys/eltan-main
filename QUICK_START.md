# ELTAN Quick Start Guide

## 🚀 Step 1: Basic Setup (Start Here!)

### 1. Install Basic Requirements
```bash
pip install -r requirements_step1.txt
```

### 2. Update Your Settings
Use the modern settings file temporarily:
```bash
export DJANGO_SETTINGS_MODULE=eltanweb.settings_modern
```

Or add this to your `.env` file:
```env
DJANGO_SETTINGS_MODULE=eltanweb.settings_modern
```

### 3. Create Migrations
```bash
python manage.py makemigrations core
python manage.py makemigrations payments  # Optional for now
python manage.py migrate
```

### 4. Test the Setup
```bash
python manage.py runserver
```

Visit: `http://localhost:8000/admin/` to access the new admin panel

## ✅ What You Get Immediately

1. **Enhanced Admin Panel**
   - Site Settings management
   - Contact Messages management
   - Modern Django admin interface

2. **Basic CMS Features**
   - Global site settings
   - Contact form handling
   - Template context with site settings

3. **Payment Integration Ready**
   - Paystack integration code ready
   - Just add your API keys to `.env`

## 🔧 Step 2: Add More Features (Optional)

Once Step 1 is working, you can gradually add more features:

### Install Additional Packages
```bash
pip install django-taggit django-import-export
pip install django-reversion django-extensions
```

### Enable Advanced Features
Replace the minimal models with full-featured ones:
```bash
mv core/models_full.py core/models.py
mv core/admin_full.py core/admin.py
```

### Add Material Admin (Optional)
```bash
pip install django-material-admin
```

Then update `INSTALLED_APPS` in settings to include material admin.

## 📋 Environment Variables

Add these to your `.env` file:

```env
# Paystack API Keys
PAYSTACK_PUBLIC_KEY=pk_test_your_key_here
PAYSTACK_SECRET_KEY=sk_test_your_key_here

# Site URL
SITE_URL=http://localhost:8000

# Email settings (optional)
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## 🎨 Using the Modern Templates

The modern templates are ready to use. Update your URLs to include:

```python
# In your main urls.py
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('membership.urls')),
    path('core/', include('core.urls')),  # Add this
    path('payments/', include('payments.urls')),  # Add this when ready
]
```

## 🛠️ Troubleshooting

### If you get "No module named 'core'" error:
Make sure the core app is in your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'core',
]
```

### If migrations fail:
Try:
```bash
python manage.py migrate --fake-initial
python manage.py makemigrations
python manage.py migrate
```

### If templates don't load:
Make sure your `TEMPLATES` setting includes the templates directory:

```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Add this
        # ... rest of config
    }
]
```

## 📞 Next Steps

1. **Get Step 1 working first** - Don't try to implement everything at once
2. **Add your Paystack keys** to start testing payments  
3. **Customize the site settings** in the admin panel
4. **Test the contact form** functionality
5. **Gradually add more features** as needed

## 🎯 Key Benefits You Get

- ✅ Modern admin interface
- ✅ Site-wide settings management  
- ✅ Contact form handling
- ✅ Payment processing ready
- ✅ Modern templates ready
- ✅ Mobile-responsive design
- ✅ SEO optimized structure

The system is designed to work incrementally - start with the basics and add features as you need them!