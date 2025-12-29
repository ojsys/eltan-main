"""
CMS Models for Dynamic Content Management
Material Design 3 inspired content blocks and pages
"""

from django.db import models
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from ckeditor.fields import RichTextField
from ordered_model.models import OrderedModel

User = get_user_model()


class HeroSlide(OrderedModel):
    """Slides for homepage hero carousel"""
    title = models.CharField(max_length=120, blank=True)
    subtitle = models.TextField(blank=True)
    image = models.ImageField(upload_to='homepage_slides/')
    cta_text = models.CharField(max_length=50, blank=True)
    cta_link = models.CharField(max_length=200, blank=True, help_text="URL for the CTA button")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(OrderedModel.Meta):
        ordering = ('order',)
        verbose_name = 'Hero Slide'
        verbose_name_plural = 'Hero Slides'

    def __str__(self):
        return self.title or f"Slide #{self.pk}"


class HomePage(models.Model):
    """Homepage content management"""
    # Hero Section
    hero_badge_text = models.CharField(
        max_length=100,
        default="Professional Membership Organization",
        help_text="Badge text above hero title"
    )
    hero_title = models.CharField(max_length=200, default="Welcome to ELTAN")
    hero_subtitle = models.TextField(
        blank=True,
        default="Join us in fostering excellence in English language teaching and learning across Nigeria.",
        help_text="Short description under the main title"
    )
    hero_cta_text = models.CharField(
        max_length=50,
        default="Get Started",
        help_text="Call-to-action button text"
    )
    hero_cta_link = models.CharField(
        max_length=200,
        default="/subscribe/",
        help_text="URL for the CTA button"
    )
    hero_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        help_text="Hero background or illustration"
    )

    # Secondary CTA
    secondary_cta_text = models.CharField(max_length=50, blank=True, default="Learn More")
    secondary_cta_link = models.CharField(max_length=200, blank=True, default="#features")

    # Features Section
    features_subtitle = models.CharField(
        max_length=100,
        default="What We Offer",
        help_text="Small text above features heading"
    )
    features_title = models.CharField(
        max_length=300,
        default="Empowering English Language Teachers with Resources, Community & Professional Growth",
        help_text="Main features section heading"
    )
    features_description = models.TextField(
        default="Join Nigeria's premier association for English language teachers. Access conferences, training, resources, and a vibrant community dedicated to excellence in English language teaching and learning.",
        help_text="Description under features heading"
    )

    # Content Section 1 (Professional Growth)
    content1_subtitle = models.CharField(max_length=100, default="Professional Growth")
    content1_title = models.CharField(max_length=200, default="Invest in Your Potential")
    content1_description = RichTextField(
        blank=True,
        default="Our membership provides unparalleled value through continuous learning, networking, and career development opportunities."
    )
    content1_button_text = models.CharField(max_length=50, default="Explore Benefits")
    content1_button_link = models.CharField(max_length=200, default="#features")

    # Content Section 2 (Community Impact)
    content2_subtitle = models.CharField(max_length=100, default="Community Impact")
    content2_title = models.CharField(max_length=200, default="Boost Your Career Growth Today")
    content2_description = models.TextField(
        default="Join a community of ambitious professionals who are transforming their careers and making an impact in their industries. ELTAN members benefit from exclusive opportunities, connections, and resources that accelerate professional growth."
    )
    content2_button_text = models.CharField(max_length=50, default="Get Started")
    content2_button_link = models.CharField(max_length=200, default="/register/")

    # FAQ Section
    faq_title = models.CharField(max_length=200, default="Frequently Asked Questions")
    faq_subtitle = models.TextField(
        default="Have questions about our service, we offer wide-range of services to give the best service to the community.",
        help_text="Description under FAQ heading"
    )

    # Final CTA Section
    cta_title = models.CharField(max_length=200, default="Ready to Transform Your Career?")
    cta_description = models.TextField(
        default="Join over 500 professionals who are accelerating their growth with ELTAN. Get access to exclusive events, training, and a powerful network."
    )
    cta_button_text = models.CharField(max_length=50, default="Get Started Today")
    cta_button_link = models.CharField(max_length=200, default="/register/")
    cta_secondary_button_text = models.CharField(max_length=50, default="Contact Us")
    cta_secondary_button_link = models.CharField(max_length=200, default="#contact")

    # About Section
    about_title = models.CharField(max_length=200, default="About ELTAN")
    about_content = RichTextField(blank=True)
    about_image = models.ImageField(upload_to='homepage/', blank=True)

    # Show/Hide Sections
    show_statistics = models.BooleanField(default=True)
    show_features = models.BooleanField(default=True)
    show_partners = models.BooleanField(default=True)
    show_faq = models.BooleanField(default=True)
    show_testimonials = models.BooleanField(default=False)

    # Meta
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Homepage"
        verbose_name_plural = "Homepage"

    def __str__(self):
        return "Homepage Content"

    def save(self, *args, **kwargs):
        # Ensure only one instance
        if not self.pk and HomePage.objects.exists():
            raise ValueError('Only one HomePage instance allowed')
        return super().save(*args, **kwargs)


class Feature(OrderedModel):
    """Homepage features/benefits cards"""
    icon = models.CharField(
        max_length=50,
        help_text="Material icon name (e.g., 'workspace_premium', 'event', 'school')"
    )
    title = models.CharField(max_length=100)
    description = models.TextField()
    link = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional link to more information"
    )
    image = models.ImageField(
        upload_to='features/',
        blank=True,
        help_text="Optional illustration/image"
    )
    is_active = models.BooleanField(default=True)

    class Meta(OrderedModel.Meta):
        ordering = ('order',)

    def __str__(self):
        return self.title


class Statistic(OrderedModel):
    """Homepage statistics/numbers"""
    ICON_CHOICES = [
        ('people', 'People/Members'),
        ('event', 'Events'),
        ('school', 'Training'),
        ('workspace_premium', 'Certifications'),
        ('trending_up', 'Growth'),
        ('location_city', 'Chapters'),
    ]

    icon = models.CharField(max_length=50, choices=ICON_CHOICES)
    number = models.CharField(
        max_length=20,
        help_text="e.g., '500+', '10K', '95%'"
    )
    label = models.CharField(
        max_length=100,
        help_text="e.g., 'Active Members', 'Annual Events'"
    )
    suffix = models.CharField(
        max_length=10,
        blank=True,
        help_text="e.g., '+', 'K', '%'"
    )
    color = models.CharField(
        max_length=7,
        default="#E67918",
        help_text="Hex color code"
    )
    is_active = models.BooleanField(default=True)

    class Meta(OrderedModel.Meta):
        ordering = ('order',)
        verbose_name_plural = "Statistics"

    def __str__(self):
        return f"{self.number} {self.label}"


class Partner(OrderedModel):
    """Partners and sponsors logos"""
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='partners/')
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(OrderedModel.Meta):
        ordering = ('order',)

    def __str__(self):
        return self.name


class FAQ(OrderedModel):
    """Frequently Asked Questions"""
    question = models.CharField(max_length=300)
    answer = RichTextField()
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., 'Membership', 'Conferences', 'General'"
    )
    is_active = models.BooleanField(default=True)

    class Meta(OrderedModel.Meta):
        ordering = ('order',)
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class Testimonial(OrderedModel):
    """Member testimonials"""
    name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=100,
        help_text="e.g., 'ELTAN Member', 'Conference Attendee'"
    )
    content = models.TextField()
    image = models.ImageField(
        upload_to='testimonials/',
        blank=True,
        help_text="Member photo"
    )
    rating = models.IntegerField(
        default=5,
        help_text="1-5 stars"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(OrderedModel.Meta):
        ordering = ('order',)

    def __str__(self):
        return f"{self.name} - {self.role}"


class Page(models.Model):
    """Dynamic pages with block-based content"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    content = RichTextField(blank=True)
    meta_description = models.TextField(
        max_length=160,
        blank=True,
        help_text="SEO meta description"
    )
    meta_keywords = models.CharField(
        max_length=200,
        blank=True,
        help_text="Comma-separated keywords"
    )

    # Templates
    TEMPLATE_CHOICES = [
        ('default', 'Default Template'),
        ('full_width', 'Full Width'),
        ('sidebar', 'With Sidebar'),
        ('cards', 'Card Layout'),
    ]
    template = models.CharField(
        max_length=20,
        choices=TEMPLATE_CHOICES,
        default='default'
    )

    # Status
    is_published = models.BooleanField(default=False)
    show_in_menu = models.BooleanField(default=False)
    menu_order = models.IntegerField(default=0)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Author
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['menu_order', 'title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class ContentBlock(models.Model):
    """Reusable content blocks for pages"""
    BLOCK_TYPES = [
        ('text', 'Text Content'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('cards', 'Card Grid'),
        ('stats', 'Statistics'),
        ('cta', 'Call to Action'),
        ('gallery', 'Image Gallery'),
        ('form', 'Form'),
    ]

    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name='blocks'
    )
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES)
    title = models.CharField(max_length=200, blank=True)
    content = RichTextField(blank=True)
    image = models.ImageField(upload_to='blocks/', blank=True)

    # Additional settings (JSON-like)
    css_classes = models.CharField(
        max_length=200,
        blank=True,
        help_text="Additional CSS classes"
    )
    background_color = models.CharField(
        max_length=7,
        blank=True,
        help_text="Hex color code"
    )

    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.block_type} - {self.title or 'Untitled'}"


class Announcement(models.Model):
    """Site-wide announcements banner"""
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    link_text = models.CharField(max_length=50, blank=True)

    TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]
    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default='info'
    )

    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message[:50]


class SocialLink(OrderedModel):
    """Social media links"""
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter/X'),
        ('linkedin', 'LinkedIn'),
        ('instagram', 'Instagram'),
        ('youtube', 'YouTube'),
        ('whatsapp', 'WhatsApp'),
    ]

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    url = models.URLField()
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Override default icon with Material icon name"
    )
    is_active = models.BooleanField(default=True)

    class Meta(OrderedModel.Meta):
        ordering = ('order',)

    def __str__(self):
        return f"{self.platform} - {self.url}"
