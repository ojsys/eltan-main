from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


GENDER_CHOICES = (
    ('Select Gender', 'Select Gender'),
    ('M', 'Male'),
    ('F', 'Female'),
)

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)
    

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    eltan_number = models.PositiveIntegerField(unique=True, blank=True, null=True)
    is_subscribed = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'gender']

    objects = CustomUserManager()

    class Meta:
        ordering = ['-date_joined']
        verbose_name_plural = 'ELTAN Users'

    def __str__(self):
        return f"{self.id} | {self.first_name} {self.last_name} | {self.email} | {self.gender} | {self.date_joined.date()} | ELTAN: {self.eltan_number or 'Not Assigned'}"

    def save(self, *args, **kwargs):
        if self.is_subscribed and not self.eltan_number:
            last_eltan = CustomUser.objects.filter(eltan_number__isnull=False).order_by('-eltan_number').first()
            self.eltan_number = (last_eltan.eltan_number + 1) if last_eltan else 1  # Start from 1000
        super().save(*args, **kwargs)
