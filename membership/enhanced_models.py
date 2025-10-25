"""
Enhanced membership models with modern CMS features
This will replace/enhance the existing models.py
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils import timezone
from ckeditor.fields import RichTextField
from taggit.managers import TaggableManager
from core.models import TimestampedModel, SEOModel, PublishableModel
import uuid
from datetime import date, timedelta
from decimal import Decimal

User = get_user_model()


class MembershipType(TimestampedModel):
    """Enhanced membership types"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = RichTextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.IntegerField(default=12, help_text="Membership duration in months")
    benefits = RichTextField(blank=True, help_text="List of membership benefits")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    # New features
    max_registrations = models.IntegerField(null=True, blank=True, help_text="Max number of registrations (null = unlimited)")
    early_bird_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    early_bird_deadline = models.DateField(null=True, blank=True)
    color_code = models.CharField(max_length=7, default="#1976d2", help_text="Hex color for UI")
    icon = models.CharField(max_length=50, blank=True, help_text="Material icon name")
    
    class Meta:
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_current_price(self):
        """Get current price considering early bird offers"""
        if (self.early_bird_price and self.early_bird_deadline and 
            date.today() <= self.early_bird_deadline):
            return self.early_bird_price
        return self.price
    
    @property
    def is_early_bird_active(self):
        return (self.early_bird_price and self.early_bird_deadline and 
                date.today() <= self.early_bird_deadline)


class EnhancedSubscription(TimestampedModel):
    """Enhanced subscription model with automated payment processing"""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    MEMBERSHIP_STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    membership_type = models.ForeignKey(MembershipType, on_delete=models.CASCADE)
    eltan_number = models.CharField(max_length=20, unique=True, blank=True)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    eltan_year = models.CharField(max_length=20, blank=True)
    
    # Payment Information
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, default='paystack')
    payment_reference = models.CharField(max_length=100, unique=True)
    paystack_reference = models.CharField(max_length=100, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_verified = models.BooleanField(default=False)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    membership_status = models.CharField(max_length=20, choices=MEMBERSHIP_STATUS_CHOICES, default='active')
    
    # Auto-renewal
    auto_renew = models.BooleanField(default=True)
    renewal_reminded = models.BooleanField(default=False)
    
    # Additional Information
    state_chapter = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True, help_text="Admin notes")
    
    # Files
    payment_proof = models.FileField(
        upload_to='payment_proofs/', 
        null=True, blank=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])]
    )
    certificate_issued = models.BooleanField(default=False)
    certificate_issued_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Membership Subscription'
        verbose_name_plural = 'Membership Subscriptions'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.membership_type.name} ({self.eltan_year})"
    
    def save(self, *args, **kwargs):
        # Generate ELTAN number if not exists
        if not self.eltan_number:
            self.eltan_number = self.generate_eltan_number()
        
        # Set payment reference if not exists
        if not self.payment_reference:
            self.payment_reference = f"ELTAN-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate end date
        if not self.end_date and self.start_date:
            self.end_date = self.start_date + timedelta(days=self.membership_type.duration_months * 30)
        
        # Set ELTAN year
        if not self.eltan_year:
            self.eltan_year = self.calculate_eltan_year()
        
        super().save(*args, **kwargs)
    
    def generate_eltan_number(self):
        """Generate unique ELTAN membership number"""
        year = date.today().year
        last_subscription = EnhancedSubscription.objects.filter(
            eltan_number__startswith=f"ELTAN{year}"
        ).order_by('eltan_number').last()
        
        if last_subscription:
            last_number = int(last_subscription.eltan_number[-4:])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f"ELTAN{year}{new_number:04d}"
    
    def calculate_eltan_year(self):
        """Calculate ELTAN year based on start date"""
        start_year = self.start_date.year
        if self.start_date.month >= 9:  # September onwards
            return f"{start_year}/{start_year + 1}"
        else:
            return f"{start_year - 1}/{start_year}"
    
    @property
    def is_active(self):
        return (self.payment_status == 'paid' and 
                self.membership_status == 'active' and 
                self.end_date >= date.today())
    
    @property
    def is_expired(self):
        return self.end_date < date.today()
    
    @property
    def days_remaining(self):
        if self.end_date >= date.today():
            return (self.end_date - date.today()).days
        return 0
    
    def get_payment_url(self):
        """Get Paystack payment URL"""
        return reverse('payment-initialize', kwargs={'subscription_id': self.id})


class PaymentLog(TimestampedModel):
    """Log all payment attempts and webhook responses"""
    subscription = models.ForeignKey(EnhancedSubscription, on_delete=models.CASCADE, related_name='payment_logs')
    event_type = models.CharField(max_length=50)  # 'charge.success', 'charge.failed', etc.
    paystack_reference = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    status = models.CharField(max_length=50)
    gateway_response = models.TextField()
    raw_data = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subscription.user.email} - {self.event_type} - {self.amount}"


class EnhancedNews(TimestampedModel, SEOModel, PublishableModel):
    """Enhanced news model with CMS features"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    excerpt = models.TextField(max_length=300, blank=True)
    content = RichTextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    featured_image = models.ImageField(upload_to='news/', blank=True)
    category = models.CharField(
        max_length=50,
        choices=[
            ('general', 'General'),
            ('conference', 'Conference'),
            ('membership', 'Membership'),
            ('research', 'Research'),
            ('teaching', 'Teaching'),
        ],
        default='general'
    )
    
    # Engagement metrics
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    
    tags = TaggableManager(blank=True)
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name_plural = 'News'
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.excerpt and self.content:
            # Auto-generate excerpt from content
            from django.utils.html import strip_tags
            self.excerpt = strip_tags(self.content)[:297] + "..."
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('news-detail', kwargs={'slug': self.slug})


class EnhancedEvent(TimestampedModel, SEOModel, PublishableModel):
    """Enhanced events model"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    description = RichTextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    venue = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    is_online = models.BooleanField(default=False)
    meeting_link = models.URLField(blank=True)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_participants = models.IntegerField(null=True, blank=True)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    
    # Images
    featured_image = models.ImageField(upload_to='events/', blank=True)
    gallery = models.ManyToManyField('EventImage', blank=True)
    
    # Files
    documents = models.ManyToManyField('EventDocument', blank=True)
    
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    
    tags = TaggableManager(blank=True)
    
    class Meta:
        ordering = ['start_date']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    @property
    def is_upcoming(self):
        return self.start_date > timezone.now()
    
    @property
    def is_ongoing(self):
        now = timezone.now()
        return self.start_date <= now <= self.end_date
    
    @property
    def is_past(self):
        return self.end_date < timezone.now()
    
    @property
    def registration_open(self):
        if self.registration_deadline:
            return timezone.now() < self.registration_deadline
        return self.is_upcoming
    
    def get_absolute_url(self):
        return reverse('event-detail', kwargs={'slug': self.slug})


class EventImage(TimestampedModel):
    """Event gallery images"""
    image = models.ImageField(upload_to='events/gallery/')
    caption = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return self.caption or f"Event Image {self.id}"


class EventDocument(TimestampedModel):
    """Event documents"""
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='events/documents/')
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.title


class EnhancedResource(TimestampedModel, SEOModel, PublishableModel):
    """Enhanced resources with categories and access control"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    description = RichTextField()
    file = models.FileField(upload_to='resources/')
    thumbnail = models.ImageField(upload_to='resources/thumbnails/', blank=True)
    
    category = models.CharField(
        max_length=50,
        choices=[
            ('journal', 'Journal'),
            ('research', 'Research'),
            ('teaching', 'Teaching Materials'),
            ('conference', 'Conference Papers'),
            ('policy', 'Policy Documents'),
            ('toolkit', 'Toolkit'),
        ],
        default='journal'
    )
    
    # Access control
    access_level = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('members', 'Members Only'),
            ('premium', 'Premium Members'),
        ],
        default='public'
    )
    
    # Metrics
    downloads = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = TaggableManager(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def can_access(self, user):
        """Check if user can access this resource"""
        if self.access_level == 'public':
            return True
        if not user.is_authenticated:
            return False
        if self.access_level == 'members':
            return hasattr(user, 'subscriptions') and user.subscriptions.filter(
                membership_status='active', 
                payment_status='paid'
            ).exists()
        if self.access_level == 'premium':
            return hasattr(user, 'subscriptions') and user.subscriptions.filter(
                membership_status='active', 
                payment_status='paid',
                membership_type__name__icontains='premium'
            ).exists()
        return False
    
    def get_absolute_url(self):
        return reverse('resource-detail', kwargs={'slug': self.slug})


class ResourceRating(TimestampedModel):
    """Resource ratings by users"""
    resource = models.ForeignKey(EnhancedResource, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['resource', 'user']
    
    def __str__(self):
        return f"{self.user.get_full_name()} rated {self.resource.title} - {self.rating}/5"