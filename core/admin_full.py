from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.forms import Textarea
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import (
    SiteSettings, Page, Banner, FAQ, Testimonial, Partner, 
    ContactMessage, Newsletter, EmailTemplate
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Enhanced site settings admin with better organization"""
    fieldsets = (
        ('Basic Information', {
            'fields': ('site_name', 'site_tagline', 'site_description')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone', 'contact_address'),
            'classes': ['collapse']
        }),
        ('Social Media', {
            'fields': ('facebook_url', 'twitter_url', 'linkedin_url', 'instagram_url', 'youtube_url'),
            'classes': ['collapse']
        }),
        ('Analytics & Tracking', {
            'fields': ('google_analytics_id', 'google_tag_manager_id', 'facebook_pixel_id'),
            'classes': ['collapse']
        }),
        ('Design Settings', {
            'fields': ('primary_color', 'secondary_color', 'accent_color'),
            'classes': ['collapse']
        }),
        ('Media', {
            'fields': ('logo', 'favicon', 'default_og_image'),
            'classes': ['collapse']
        }),
        ('Membership Settings', {
            'fields': ('membership_fee_regular', 'membership_fee_student', 'current_eltan_year'),
            'classes': ['collapse']
        }),
        ('Payment Settings', {
            'fields': ('paystack_public_key', 'enable_online_payment'),
            'classes': ['collapse']
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Enhanced page admin with SEO and publishing features"""
    list_display = ['title', 'slug', 'status', 'show_in_menu', 'sort_order', 'created_at', 'page_actions']
    list_filter = ['status', 'show_in_menu', 'template_name', 'created_at']
    search_fields = ['title', 'content', 'meta_title', 'meta_description']
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'content')
        }),
        ('Settings', {
            'fields': ('template_name', 'parent', 'sort_order', 'show_in_menu')
        }),
        ('Publishing', {
            'fields': ('status', 'featured', 'published_at'),
            'classes': ['collapse']
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ['collapse']
        }),
        ('Tags', {
            'fields': ['tags'],
            'classes': ['collapse']
        }),
    )
    
    def page_actions(self, obj):
        """Custom action buttons"""
        if obj.pk:
            view_url = obj.get_absolute_url()
            return format_html(
                '<a class="button" href="{}" target="_blank">View Page</a>',
                view_url
            )
        return "Save first"
    page_actions.short_description = 'Actions'


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    """Banner management for homepage"""
    list_display = ['title', 'sort_order', 'is_active', 'banner_preview', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'subtitle']
    list_editable = ['sort_order', 'is_active']
    
    def banner_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 100px; height: 60px; object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return "No image"
    banner_preview.short_description = 'Preview'


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """FAQ management"""
    list_display = ['question', 'category', 'sort_order', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['question', 'answer']
    list_editable = ['sort_order', 'is_active']


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    """Testimonial management"""
    list_display = ['name', 'organization', 'rating', 'is_active', 'featured', 'testimonial_preview']
    list_filter = ['rating', 'is_active', 'featured']
    search_fields = ['name', 'organization', 'content']
    list_editable = ['is_active', 'featured']
    
    def testimonial_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 50%;" />',
                obj.image.url
            )
        return "No photo"
    testimonial_preview.short_description = 'Photo'


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    """Partner and sponsor management"""
    list_display = ['name', 'category', 'sort_order', 'is_active', 'logo_preview']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['sort_order', 'is_active']
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="width: 80px; height: 40px; object-fit: contain;" />',
                obj.logo.url
            )
        return "No logo"
    logo_preview.short_description = 'Logo'


class ContactMessageResource(resources.ModelResource):
    class Meta:
        model = ContactMessage
        export_order = ['created_at', 'name', 'email', 'phone', 'subject', 'message', 'is_read', 'replied']


@admin.register(ContactMessage)
class ContactMessageAdmin(ImportExportModelAdmin):
    """Contact message management with export functionality"""
    resource_class = ContactMessageResource
    list_display = ['subject', 'name', 'email', 'created_at', 'is_read', 'replied', 'message_actions']
    list_filter = ['is_read', 'replied', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['name', 'email', 'phone', 'subject', 'message', 'created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Message Details', {
            'fields': ('name', 'email', 'phone', 'subject', 'message', 'created_at')
        }),
        ('Response', {
            'fields': ('is_read', 'replied', 'reply_message', 'replied_at')
        }),
    )
    
    def message_actions(self, obj):
        """Custom action buttons"""
        actions = []
        if not obj.is_read:
            actions.append(
                format_html('<span style="color: #e74c3c; font-weight: bold;">●</span> New')
            )
        if obj.replied:
            actions.append('✅ Replied')
        return format_html(' | '.join(actions)) if actions else '-'
    message_actions.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if change and 'is_read' in form.changed_data and obj.is_read:
            # Mark as read timestamp
            from django.utils import timezone
            if not obj.replied_at and obj.reply_message:
                obj.replied_at = timezone.now()
                obj.replied = True
        super().save_model(request, obj, form, change)


class NewsletterResource(resources.ModelResource):
    class Meta:
        model = Newsletter
        export_order = ['email', 'name', 'is_active', 'confirmed', 'created_at']


@admin.register(Newsletter)
class NewsletterAdmin(ImportExportModelAdmin):
    """Newsletter subscription management"""
    resource_class = NewsletterResource
    list_display = ['email', 'name', 'is_active', 'confirmed', 'created_at']
    list_filter = ['is_active', 'confirmed', 'created_at']
    search_fields = ['email', 'name']
    list_editable = ['is_active']
    actions = ['mark_confirmed', 'mark_unconfirmed', 'export_active_emails']
    
    def mark_confirmed(self, request, queryset):
        count = queryset.update(confirmed=True)
        self.message_user(request, f'{count} subscribers marked as confirmed.')
    mark_confirmed.short_description = 'Mark selected as confirmed'
    
    def mark_unconfirmed(self, request, queryset):
        count = queryset.update(confirmed=False)
        self.message_user(request, f'{count} subscribers marked as unconfirmed.')
    mark_unconfirmed.short_description = 'Mark selected as unconfirmed'
    
    def export_active_emails(self, request, queryset):
        """Export active email addresses only"""
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="active_emails.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Email', 'Name'])
        
        for newsletter in queryset.filter(is_active=True, confirmed=True):
            writer.writerow([newsletter.email, newsletter.name])
        
        return response
    export_active_emails.short_description = 'Export active emails as CSV'


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Email template management"""
    list_display = ['name', 'template_type', 'subject', 'is_active']
    list_filter = ['template_type', 'is_active']
    search_fields = ['name', 'subject', 'content']
    
    fieldsets = (
        ('Template Details', {
            'fields': ('name', 'template_type', 'subject', 'is_active')
        }),
        ('Email Content', {
            'fields': ('content',),
            'description': 'Available variables: {{user_name}}, {{site_name}}, {{membership_type}}, {{eltan_number}}, {{payment_amount}}, {{expiry_date}}'
        }),
    )


# Customize admin site
admin.site.site_header = "ELTAN CMS Administration"
admin.site.site_title = "ELTAN CMS"
admin.site.index_title = "Welcome to ELTAN Content Management System"

# Add some custom CSS for better admin experience
class CustomAdminMixin:
    """Mixin to add custom styling to admin"""
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/custom_admin.js',)