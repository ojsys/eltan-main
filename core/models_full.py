from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from ckeditor.fields import RichTextField
from taggit.managers import TaggableManager
import uuid

User = get_user_model()


class TimestampedModel(models.Model):
    """Abstract base class with timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class SEOModel(models.Model):
    """Abstract base class for SEO fields"""
    meta_title = models.CharField(max_length=150, blank=True, help_text="SEO title (max 150 chars)")
    meta_description = models.TextField(max_length=300, blank=True, help_text="SEO description (max 300 chars)")
    meta_keywords = models.CharField(max_length=255, blank=True, help_text="SEO keywords, comma-separated")
    
    class Meta:
        abstract = True


class PublishableModel(models.Model):
    """Abstract base class for publishable content"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    featured = models.BooleanField(default=False, help_text="Feature this content on homepage")
    
    class Meta:
        abstract = True


class SiteSettings(models.Model):
    """Global site settings - CMS functionality"""
    site_name = models.CharField(max_length=100, default="ELTAN")
    site_tagline = models.CharField(max_length=200, blank=True)
    site_description = models.TextField(blank=True)
    
    # Contact Information
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_address = models.TextField(blank=True)
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    
    # SEO
    google_analytics_id = models.CharField(max_length=50, blank=True)
    google_tag_manager_id = models.CharField(max_length=50, blank=True)
    facebook_pixel_id = models.CharField(max_length=50, blank=True)
    
    # Design Settings
    primary_color = models.CharField(max_length=7, default="#1976d2", help_text="Hex color code")
    secondary_color = models.CharField(max_length=7, default="#dc004e", help_text="Hex color code")
    accent_color = models.CharField(max_length=7, default="#e67918", help_text="Hex color code")
    
    # Logo and Images
    logo = models.ImageField(upload_to='site/', blank=True)
    favicon = models.ImageField(upload_to='site/', blank=True)
    default_og_image = models.ImageField(upload_to='site/', blank=True, help_text="Default social sharing image")
    
    # Membership Settings
    membership_fee_regular = models.DecimalField(max_digits=10, decimal_places=2, default=5500)
    membership_fee_student = models.DecimalField(max_digits=10, decimal_places=2, default=3000)
    current_eltan_year = models.CharField(max_length=20, blank=True)
    
    # Payment Settings
    paystack_public_key = models.CharField(max_length=100, blank=True)
    enable_online_payment = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return self.site_name
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SiteSettings.objects.exists():
            raise ValueError('There can only be one SiteSettings instance')
        return super().save(*args, **kwargs)


class Page(TimestampedModel, SEOModel, PublishableModel):
    """CMS Pages"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    content = RichTextField()
    template_name = models.CharField(
        max_length=100, 
        choices=[
            ('default', 'Default Page'),
            ('home', 'Homepage'),
            ('about', 'About Page'),
            ('contact', 'Contact Page'),
        ],
        default='default'
    )
    sort_order = models.IntegerField(default=0)
    show_in_menu = models.BooleanField(default=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    tags = TaggableManager(blank=True)
    
    class Meta:
        ordering = ['sort_order', 'title']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('page-detail', kwargs={'slug': self.slug})


class Banner(TimestampedModel):
    """Homepage banners/slides"""
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to='banners/')
    mobile_image = models.ImageField(upload_to='banners/', blank=True, help_text="Mobile-optimized image")
    link_text = models.CharField(max_length=50, blank=True)
    link_url = models.URLField(blank=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['sort_order']
    
    def __str__(self):
        return self.title


class FAQ(TimestampedModel):
    """Frequently Asked Questions"""
    question = models.CharField(max_length=300)
    answer = RichTextField()
    category = models.CharField(
        max_length=50,
        choices=[
            ('membership', 'Membership'),
            ('conference', 'Conference'),
            ('general', 'General'),
            ('payment', 'Payment'),
        ],
        default='general'
    )
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['category', 'sort_order']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'
    
    def __str__(self):
        return self.question


class Testimonial(TimestampedModel):
    """Member testimonials"""
    name = models.CharField(max_length=100)
    position = models.CharField(max_length=200, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='testimonials/', blank=True)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-featured', '-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.organization}"


class Partner(TimestampedModel):
    """Partners and sponsors"""
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='partners/')
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=50,
        choices=[
            ('platinum', 'Platinum Partner'),
            ('gold', 'Gold Partner'),
            ('silver', 'Silver Partner'),
            ('bronze', 'Bronze Partner'),
            ('sponsor', 'Sponsor'),
        ],
        default='bronze'
    )
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['category', 'sort_order']
    
    def __str__(self):
        return self.name


class ContactMessage(TimestampedModel):
    """Contact form submissions"""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    replied = models.BooleanField(default=False)
    reply_message = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"


class Newsletter(TimestampedModel):
    """Newsletter subscriptions"""
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    confirmed = models.BooleanField(default=False)
    confirmation_token = models.UUIDField(default=uuid.uuid4)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.email


class EmailTemplate(TimestampedModel):
    """Email templates for automated emails"""
    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=200)
    content = RichTextField()
    template_type = models.CharField(
        max_length=50,
        choices=[
            ('welcome', 'Welcome Email'),
            ('payment_confirmation', 'Payment Confirmation'),
            ('certificate', 'Certificate Ready'),
            ('newsletter', 'Newsletter'),
            ('reminder', 'Membership Reminder'),
        ]
    )
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name