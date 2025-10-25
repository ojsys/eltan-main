# Admin Login Credentials

## Current Superuser Account

**Login URL**: http://localhost:8000/admin

```
Email: onahjonah@gmail.com
Password: admin123
```

⚠️ **IMPORTANT SECURITY NOTE**:
- This is a temporary password that was reset for development purposes
- Change this password immediately after logging in
- Never use simple passwords like this in production

## Changing Your Password

### After Login (Recommended):
1. Login to admin panel: http://localhost:8000/admin
2. Click on your email in the top right corner
3. Click "Change password"
4. Enter current password: `admin123`
5. Enter and confirm new strong password
6. Click "Change my password"

### Via Command Line:
```bash
export ELTAN_ENV=development
export DJANGO_SETTINGS_MODULE=eltanweb.settings.development
python manage.py changepassword onahjonah@gmail.com
```

## Creating Additional Admin Users

### Method 1: Using Django Admin Panel
1. Login to http://localhost:8000/admin
2. Go to "Account" → "Users"
3. Click "Add User +"
4. Fill in the form
5. Check "Staff status" and "Superuser status"
6. Save

### Method 2: Using Command Line
```bash
export ELTAN_ENV=development
export DJANGO_SETTINGS_MODULE=eltanweb.settings.development
python manage.py createsuperuser
```

Follow the prompts to enter:
- Email address
- First name
- Last name
- Gender
- Password (entered twice)

### Method 3: Using Python Script
```bash
export ELTAN_ENV=development
export DJANGO_SETTINGS_MODULE=eltanweb.settings.development
python manage.py shell
```

Then paste this code:
```python
from account.models import CustomUser

# Create a new superuser
user = CustomUser.objects.create_user(
    email='admin@eltan.ng',
    first_name='Admin',
    last_name='User',
    gender='male',  # or 'female'
    password='your_secure_password_here'
)
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.save()

print(f"✅ Superuser created: {user.email}")
```

## Resetting Forgotten Passwords

If you forget your password, run this script:

```bash
export ELTAN_ENV=development
export DJANGO_SETTINGS_MODULE=eltanweb.settings.development
python manage.py shell << 'EOF'
from account.models import CustomUser

# Replace with the email you want to reset
email = 'onahjonah@gmail.com'
new_password = 'admin123'  # Change this to your desired password

user = CustomUser.objects.get(email=email)
user.set_password(new_password)
user.save()

print(f"✅ Password reset for {email}")
print(f"New password: {new_password}")
EOF
```

## Troubleshooting Login Issues

### Issue: "Invalid email or password"
**Solutions**:
1. Make sure you're using the email address (not username)
2. Check that `is_active = True` for the user
3. Reset the password using the script above

### Issue: "You don't have permission to access this page"
**Solutions**:
1. Make sure `is_staff = True` for the user
2. For full admin access, ensure `is_superuser = True`

### Issue: Can't access certain admin sections
**Solutions**:
1. Check user has `is_superuser = True`
2. Or assign specific permissions in admin panel

## Checking User Status

To check a user's current status:
```bash
export ELTAN_ENV=development
export DJANGO_SETTINGS_MODULE=eltanweb.settings.development
python manage.py shell << 'EOF'
from account.models import CustomUser

email = 'onahjonah@gmail.com'
user = CustomUser.objects.get(email=email)

print(f"Email: {user.email}")
print(f"Is active: {user.is_active}")
print(f"Is staff: {user.is_staff}")
print(f"Is superuser: {user.is_superuser}")
print(f"Last login: {user.last_login}")
EOF
```

## Security Best Practices

1. **Use Strong Passwords**:
   - At least 12 characters
   - Mix of uppercase, lowercase, numbers, symbols
   - Don't reuse passwords

2. **Change Default Passwords**:
   - Always change temporary passwords immediately
   - Never use `admin123` or similar in production

3. **Limit Superuser Accounts**:
   - Only create superusers when necessary
   - Use regular staff accounts with specific permissions when possible

4. **Regular Audits**:
   - Periodically review active admin accounts
   - Deactivate accounts of users who no longer need access

5. **Production Settings**:
   - In production, ensure `DEBUG = False`
   - Use environment variables for sensitive data
   - Enable SSL/HTTPS (already configured in production.py)

---

**Generated**: 2025-10-24
**Environment**: Development (SQLite)

**Note**: These credentials are for development only. Production credentials should be managed securely and never committed to version control.
