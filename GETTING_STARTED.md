# 🚀 GETTING STARTED - ELTAN Material Design Redesign

## Quick Start Guide

Follow these steps in order to activate the new Material Design interface.

---

## Step 1: Install New Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate  # On Mac/Linux
# OR
venv\Scripts\activate  # On Windows

# Install new required packages
pip install django-ordered-model==3.7.4
pip install Pillow==10.2.0

# Optional: Install Material Design Admin (enhanced admin interface)
pip install django-material-admin==1.8.6
```

**OR** install all at once:
```bash
pip install -r requirements/development.txt
```

---

## Step 2: Enable Material Admin (Optional)

If you installed `django-material-admin`, uncomment these lines in `eltanweb/settings/base.py`:

```python
INSTALLED_APPS = [
    # Uncomment these two lines:
    'material',
    'material.admin',

    # Rest of the apps...
]
```

---

## Step 3: Create Database Migrations

```bash
# Set environment to development
export ELTAN_ENV=development  # On Mac/Linux
# OR
set ELTAN_ENV=development  # On Windows

# Create migrations for new CMS models
python manage.py makemigrations core

# Create migrations for enhanced membership models
python manage.py makemigrations membership

# Apply all migrations
python manage.py migrate
```

---

## Step 4: Create Initial CMS Content

```bash
# Start Django shell
python manage.py shell
```

Then paste this code:

```python
from core.models_cms import HomePage, Feature, Statistic, FAQ
from core.models import SiteSettings

# Create Homepage
home, created = HomePage.objects.get_or_create(
    id=1,
    defaults={
        'hero_title': 'You can Control All your Professional Growth through ELTAN',
        'hero_subtitle': 'Join Nigeria\'s premier leadership training organization. Access exclusive conferences, professional development resources, and a thriving community of emerging leaders.',
        'hero_cta_text': 'Get Started',
        'hero_cta_link': '/subscribe/',
        'secondary_cta_text': 'Learn More',
        'secondary_cta_link': '/about/',
        'about_title': 'About ELTAN',
        'about_content': 'Emerging Leaders Training and Nurturing (ELTAN) is committed to developing professional excellence across Nigeria.',
        'show_statistics': True,
        'show_features': True,
        'show_partners': False,
        'show_faq': True,
        'is_active': True
    }
)
print(f"Homepage {'created' if created else 'already exists'}")

# Create Features
features_data = [
    {
        'icon': 'event_available',
        'title': 'Professional Conferences',
        'description': 'Attend exclusive conferences with industry leaders, gain insights, and network with peers across Nigeria.',
        'order': 1
    },
    {
        'icon': 'school',
        'title': 'Continuous Training',
        'description': 'Access world-class training programs, workshops, and CPD opportunities to enhance your professional skills.',
        'order': 2
    },
    {
        'icon': 'diversity_3',
        'title': 'Vibrant Community',
        'description': 'Join Special Interest Groups (SIGs), connect with like-minded professionals, and grow your network.',
        'order': 3
    },
]

for feat_data in features_data:
    feat, created = Feature.objects.get_or_create(
        title=feat_data['title'],
        defaults={
            'icon': feat_data['icon'],
            'description': feat_data['description'],
            'order': feat_data['order'],
            'is_active': True
        }
    )
    print(f"Feature '{feat.title}' {'created' if created else 'exists'}")

# Create Statistics
stats_data = [
    {'icon': 'people', 'number': '500+', 'label': 'Active Members', 'order': 1},
    {'icon': 'event', 'number': '12', 'label': 'Annual Events', 'order': 2},
    {'icon': 'location_city', 'number': '36', 'label': 'State Chapters', 'order': 3},
    {'icon': 'workspace_premium', 'number': '95%', 'label': 'Satisfaction Rate', 'order': 4},
]

for stat_data in stats_data:
    stat, created = Statistic.objects.get_or_create(
        label=stat_data['label'],
        defaults={
            'icon': stat_data['icon'],
            'number': stat_data['number'],
            'color': '#E67918',
            'order': stat_data['order'],
            'is_active': True
        }
    )
    print(f"Statistic '{stat.label}' {'created' if created else 'exists'}")

# Create FAQs
faqs_data = [
    {
        'question': 'How do I get started with ELTAN membership?',
        'answer': 'Getting started is easy! Simply click the "Join Now" button, fill out the registration form, and choose your membership category. After payment verification, you\'ll receive your unique ELTAN number and full access to member benefits.',
        'order': 1
    },
    {
        'question': 'What are the membership fees?',
        'answer': 'New members pay ₦5,500 for the first year, while renewal members pay ₦3,000 annually. All payments are processed through secure bank transfer.',
        'order': 2
    },
]

for faq_data in faqs_data:
    faq, created = FAQ.objects.get_or_create(
        question=faq_data['question'],
        defaults={
            'answer': faq_data['answer'],
            'order': faq_data['order'],
            'is_active': True
        }
    )
    print(f"FAQ created: {created}")

# Create or update Site Settings
settings, created = SiteSettings.objects.get_or_create(
    id=1,
    defaults={
        'site_name': 'ELTAN',
        'site_tagline': 'Emerging Leaders Training and Nurturing',
        'site_description': 'Nigeria\'s premier professional membership organization',
        'primary_color': '#E67918',
        'secondary_color': '#1565C0',
        'accent_color': '#00796B',
        'membership_fee_regular': 5500,
        'membership_fee_student': 3000,
    }
)
print(f"Site Settings {'created' if created else 'updated'}")

print("\n✅ Initial CMS content created successfully!")
print("You can now customize this content from the admin panel.")
```

Press `Ctrl+D` or type `exit()` to exit the shell.

---

## Step 5: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

---

## Step 6: Run the Development Server

```bash
python manage.py runserver
```

---

## Step 7: Access the New Interface

### Admin Panel
Visit: http://localhost:8000/admin

Login with your superuser credentials and explore:
- **Core** → Homepage, Features, Statistics, FAQs
- **Membership** → Events, News, SIGs, Resources (now with enhanced fields)
- **Site Settings** → Brand colors, logos, fees

### Homepage (New Material Design)
Visit: http://localhost:8000/

**Note**: You'll need to update your views to use the new template. See Step 8.

---

## Step 8: Connect New Templates to Views

### Option A: Quick Test (Temporary URL)

Create a test view in `membership/views.py`:

```python
from django.shortcuts import render

def home_material(request):
    """Temporary view to test new Material Design homepage"""
    return render(request, 'landing/home_material.html')

def dashboard_material(request):
    """Temporary view to test new Material Design dashboard"""
    from membership.models import SigsRegistration
    user_sigs = SigsRegistration.objects.filter(user=request.user) if request.user.is_authenticated else []

    context = {
        'user_sigs': user_sigs,
        'days_remaining': 90,  # Calculate actual days
        'progress_percentage': 75,  # Calculate actual percentage
    }
    return render(request, 'dashboard/dashboard_material.html', context)
```

Add to `eltanweb/urls.py` or `membership/urls.py`:

```python
from membership.views import home_material, dashboard_material

urlpatterns = [
    # ... existing URLs
    path('new/', home_material, name='home_material'),  # Test URL
    path('dashboard/new/', dashboard_material, name='dashboard_material'),  # Test URL
]
```

Visit:
- http://localhost:8000/new/ - New homepage
- http://localhost:8000/dashboard/new/ - New dashboard

### Option B: Replace Existing Views

Update your existing views to use new templates:

```python
# Replace in your existing views
def home(request):
    return render(request, 'landing/home_material.html')

def dashboard(request):
    # ... existing logic
    return render(request, 'dashboard/dashboard_material.html', context)
```

---

## Step 9: Download Illustrations (Optional)

For the best visual experience, download free illustrations:

1. Visit https://undraw.co/illustrations
2. Search for these terms:
   - "team work" → save as `leadership.svg`
   - "presentation" → save as `conference.svg`
   - "online learning" → save as `training.svg`
   - "community" → save as `community.svg`
3. Change color to `#E67918` (ELTAN orange)
4. Download SVG files
5. Place in `static/illustrations/`

**OR** use the placeholder SVGs already created.

See `ILLUSTRATIONS_GUIDE.md` for detailed instructions.

---

## 🎉 You're Done!

Your ELTAN website now has:
- ✅ Modern Material Design 3 interface
- ✅ Comprehensive CMS from admin panel
- ✅ Enhanced models with new fields
- ✅ Beautiful new homepage
- ✅ Redesigned dashboard
- ✅ Placeholder illustrations

---

## 📚 Next Steps

1. **Customize Content**: Login to admin and update homepage content
2. **Upload Logo**: Add your logo in Site Settings
3. **Add Partners**: Create partner logos in Partners section
4. **Download Illustrations**: Replace placeholders with real illustrations
5. **Update Events/News**: Use enhanced fields (featured, published, etc.)
6. **Test All Pages**: Navigate through the site to ensure everything works

---

## 🆘 Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements/development.txt
```

### Migrations not working
```bash
python manage.py makemigrations
python manage.py migrate --run-syncdb
```

### Static files not loading
```bash
python manage.py collectstatic --clear --noinput
```

### Templates not found
Ensure 'core' is in INSTALLED_APPS and templates exist in correct directories.

---

## 📖 Documentation

- `REDESIGN_IMPLEMENTATION_SUMMARY.md` - Complete overview of changes
- `ILLUSTRATIONS_GUIDE.md` - How to download and integrate illustrations
- `ENVIRONMENT_SETUP.md` - Development vs Production setup
- `CHANGES_SUMMARY.md` - Environment separation details

---

## 🎨 Customization

### Change Colors
Visit Admin → Site Settings → Design Settings

### Edit Homepage
Visit Admin → Core → Homepage

### Add/Remove Features
Visit Admin → Core → Features

### Manage Statistics
Visit Admin → Core → Statistics

---

**Ready to start? Run:**
```bash
pip install -r requirements/development.txt
python manage.py migrate
python manage.py runserver
```

Then visit http://localhost:8000/admin
