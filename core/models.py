"""
Core models for ELTAN website
Includes site settings, contact forms, and imports CMS models
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# Import CMS models
from .models_cms import (
    HomePage, Feature, Statistic, Partner, FAQ, Testimonial,
    Page, ContentBlock, Announcement, SocialLink
)


class SiteSettings(models.Model):
    """Basic site settings"""
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
    
    # Design Settings
    primary_color = models.CharField(max_length=7, default="#1976d2")
    secondary_color = models.CharField(max_length=7, default="#dc004e")
    accent_color = models.CharField(max_length=7, default="#e67918")
    
    # Logo and Images
    logo = models.ImageField(upload_to='site/', blank=True, help_text="Main logo for header")
    footer_logo = models.ImageField(upload_to='site/', blank=True, help_text="Footer logo (optional, uses header logo if empty)")
    favicon = models.ImageField(upload_to='site/', blank=True)
    default_og_image = models.ImageField(upload_to='site/', blank=True)

    # Header Settings
    header_announcement = models.CharField(max_length=255, blank=True, help_text="Optional announcement bar text")
    show_header_announcement = models.BooleanField(default=False, help_text="Show/hide announcement bar")

    # Footer Settings
    footer_about_title = models.CharField(max_length=100, default="About ELTAN", blank=True)
    footer_about_text = models.TextField(blank=True, help_text="Brief description for footer about section")
    footer_contact_title = models.CharField(max_length=100, default="Contact Us", blank=True)
    copyright_text = models.CharField(max_length=255, default="© 2025 ELTAN. All rights reserved.", blank=True)

    # Additional Contact Details
    whatsapp_number = models.CharField(max_length=20, blank=True, help_text="WhatsApp contact number")
    office_hours = models.CharField(max_length=100, blank=True, help_text="e.g., Mon-Fri: 9AM-5PM")
    alternate_email = models.EmailField(blank=True, help_text="Secondary contact email")
    alternate_phone = models.CharField(max_length=20, blank=True, help_text="Secondary phone number")

    # Newsletter
    newsletter_title = models.CharField(max_length=100, default="Subscribe to Our Newsletter", blank=True)
    newsletter_description = models.TextField(blank=True, help_text="Newsletter signup description")

    # Membership Settings
    membership_fee_regular = models.DecimalField(max_digits=10, decimal_places=2, default=5500)
    membership_fee_student = models.DecimalField(max_digits=10, decimal_places=2, default=3000)
    current_eltan_year = models.CharField(max_length=20, blank=True)
    
    # Payment Settings
    paystack_public_key = models.CharField(max_length=100, blank=True)
    enable_online_payment = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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


class ContactMessage(models.Model):
    """Contact form submissions"""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"