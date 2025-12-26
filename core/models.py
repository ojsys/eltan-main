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
    logo = models.ImageField(upload_to='site/', blank=True)
    favicon = models.ImageField(upload_to='site/', blank=True)
    default_og_image = models.ImageField(upload_to='site/', blank=True)
    
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