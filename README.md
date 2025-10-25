# ELTAN - English Language Teachers Association of Nigeria

A comprehensive web platform for the English Language Teachers Association of Nigeria (ELTAN), built with Django. This platform manages memberships, conferences, Special Interest Groups (SIGs), events, and provides a modern admin interface for organization management.

## Features

### Membership Management
- **Dual Payment System**: Support for both Paystack (online) and Manual (bank transfer) payments
- **Membership Types**: Multiple membership tiers with different benefits
- **Member Profiles**: Comprehensive member information and profile management
- **Member Dashboard**: Personalized dashboard for members with activity tracking

### Conference Management
- **Conference Registration**: Online registration for ELTAN conferences
- **Conference Documents**: Upload and manage conference materials
- **Speaker Management**: Track and display conference speakers
- **Schedule Management**: Organize conference schedules and sessions
- **Sponsor Management**: Manage conference sponsors and partners
- **Local Organizing Committee**: Track LOC members and roles

### Special Interest Groups (SIGs)
- **SIG Creation**: Create and manage specialized interest groups
- **Member Enrollment**: Users can join/leave SIGs
- **SIG Moderation**: Assign moderators to manage each SIG
- **Member Directory**: View all members in each SIG
- **Dashboard Integration**: Display user's SIGs on their dashboard

### Content Management
- **Events**: Create and manage ELTAN events
- **News**: Publish news and updates
- **Resources**: Share educational resources with members
- **Newsletters**: Manage and distribute newsletters
- **Partners**: Display organization partners and sponsors
- **Hero Slides**: Dynamic homepage carousel
- **FAQs**: Frequently asked questions management

### Admin Features
- **Modern Admin Interface**: Jazzmin-powered admin with ELTAN branding
- **Rich Text Editing**: CKEditor integration for content management
- **Advanced Filtering**: Search and filter across all models
- **Inline Editing**: Manage related objects inline
- **Custom Icons**: Material Design icons throughout admin
- **Statistics Dashboard**: View key metrics and statistics

## Technology Stack

- **Framework**: Django 5.0.4
- **Language**: Python 3.x
- **Database**: SQLite (development) / MySQL/PostgreSQL (production)
- **Admin Interface**: django-jazzmin 3.0.1
- **Forms**: django-crispy-forms with Bootstrap 5
- **Rich Text Editor**: django-ckeditor
- **Payment Gateway**: Paystack API
- **Environment Variables**: python-decouple
- **Frontend**: Bootstrap 5, Material Design 3, Material Icons

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)
- Git

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/eltan.git
   cd eltan
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit .env and fill in your actual values
   # Required variables:
   # - SECRET_KEY
   # - PAYSTACK_SECRET_KEY
   # - PAYSTACK_PUBLIC_KEY
   # - USER_EMAIL
   # - USER_PASSWORD
   ```

5. **Generate a secret key**
   ```bash
   python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
   ```
   Copy the output and paste it as the SECRET_KEY in your .env file.

6. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

7. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

8. **Collect static files**
   ```bash
   python manage.py collectstatic
   ```

9. **Run the development server**
   ```bash
   python manage.py runserver
   ```

10. **Access the application**
    - Website: http://localhost:8000
    - Admin Panel: http://localhost:8000/admin

## Project Structure

```
eltan2/
├── account/                    # User authentication and account management
├── core/                       # Core CMS models (Hero, Partners, Features, etc.)
├── mainapp/                    # Main application views and templates
├── membership/                 # Membership, conferences, SIGs, events
│   ├── models.py              # Database models
│   ├── views.py               # View functions
│   ├── admin.py               # Admin configuration
│   ├── urls.py                # URL routing
│   └── templates/             # HTML templates
├── eltanweb/                  # Project settings and configuration
│   ├── settings/
│   │   ├── base.py           # Base settings
│   │   ├── development.py    # Development settings
│   │   └── production.py     # Production settings
│   ├── urls.py               # Main URL configuration
│   └── wsgi.py               # WSGI configuration
├── static/                    # Static files (CSS, JS, images)
├── media/                     # User-uploaded files
├── templates/                 # Global templates
├── manage.py                  # Django management script
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## Configuration

### Environment Settings

The project uses environment-specific settings:
- **Development**: `eltanweb.settings.development`
- **Production**: `eltanweb.settings.production`

Set the environment in your .env file:
```bash
DJANGO_SETTINGS_MODULE=eltanweb.settings.development
```

### Paystack Configuration

1. Sign up at https://paystack.com
2. Get your API keys from https://dashboard.paystack.com/settings/developer
3. For development, use test keys (sk_test_*, pk_test_*)
4. For production, use live keys (sk_live_*, pk_live_*)

### Email Configuration

For Gmail:
1. Enable 2-factor authentication on your Google account
2. Generate an app-specific password
3. Use the app password (not your regular password) in USER_PASSWORD

## Usage

### Admin Panel

Access the admin panel at `/admin` to manage:
- Users and permissions
- Memberships and subscriptions
- Conferences and registrations
- Special Interest Groups
- Events, news, and resources
- Site content (hero slides, partners, FAQs)

### Member Registration

1. Users register at `/register`
2. Select membership type and payment method
3. Complete payment (Paystack or manual)
4. Admin verifies manual payments
5. Members gain access to member-only features

### Conference Registration

1. Admin creates conference in admin panel
2. Users register at `/conferences/{id}/register`
3. Choose payment method
4. Complete payment process
5. Receive confirmation email

### Special Interest Groups

1. Admin creates SIGs and assigns moderators
2. Users browse SIGs at `/sigs`
3. Users join/leave SIGs
4. View SIG details and members
5. Track joined SIGs on dashboard

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Creating a New App
```bash
python manage.py startapp appname
```

### Database Backup
```bash
# SQLite
python manage.py dumpdata > backup.json

# Restore
python manage.py loaddata backup.json
```

## Production Deployment

### Pre-deployment Checklist

1. **Security**
   - [ ] Set DEBUG=False
   - [ ] Use strong SECRET_KEY
   - [ ] Configure ALLOWED_HOSTS
   - [ ] Use HTTPS
   - [ ] Use live Paystack keys

2. **Database**
   - [ ] Configure production database (MySQL/PostgreSQL)
   - [ ] Run migrations
   - [ ] Set up database backups

3. **Static Files**
   - [ ] Configure static file serving
   - [ ] Run collectstatic
   - [ ] Set up CDN (optional)

4. **Email**
   - [ ] Configure production email backend
   - [ ] Test email delivery

5. **Monitoring**
   - [ ] Set up error logging
   - [ ] Configure monitoring (Sentry, etc.)
   - [ ] Set up uptime monitoring

### Recommended Hosting

- **PythonAnywhere**: Easy Django deployment
- **Heroku**: Platform-as-a-Service with free tier
- **DigitalOcean**: VPS with full control
- **AWS Elastic Beanstalk**: Scalable cloud hosting

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, email support@eltanigeria.org or open an issue on GitHub.

## Acknowledgments

- ELTAN Leadership Team
- All contributing developers
- Django and Python communities
- Open source libraries used in this project

## Project Roadmap

### Upcoming Features
- [ ] Mobile app integration
- [ ] Advanced analytics dashboard
- [ ] Online learning platform
- [ ] Member directory search
- [ ] Real-time notifications
- [ ] Social media integration
- [ ] Certificate generation system
- [ ] Payment history and receipts

---

**ELTAN** - Empowering English Language Teachers Across Nigeria
