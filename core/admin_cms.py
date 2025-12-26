"""
Admin interfaces for CMS models
Material Design inspired admin customizations
"""

from django.contrib import admin
from ordered_model.admin import OrderedModelAdmin
from django.utils.html import format_html
from .models_cms import (
    HeroSlide, HomePage, Feature, Statistic, Partner, FAQ, Testimonial,
    Page, ContentBlock, Announcement, SocialLink
)
from .models import SiteSettings, ContactMessage


@admin.register(HomePage)
class HomePageAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Hero Section', {
            'fields': ('hero_title', 'hero_subtitle', 'hero_image',
                      'hero_cta_text', 'hero_cta_link',
                      'secondary_cta_text', 'secondary_cta_link')
        }),
        ('About Section', {
            'fields': ('about_title', 'about_content', 'about_image')
        }),
        ('Section Visibility', {
            'fields': ('show_statistics', 'show_features', 'show_partners',
                      'show_faq', 'show_testimonials')
        }),
        ('Status', {
            'fields': ('is_active', 'updated_at')
        }),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        # Only allow one instance
        if HomePage.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of homepage
        return False


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'order', 'is_active', 'move_up_down_links')
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    search_fields = ('title', 'description')
    ordering = ('order',)

    fieldsets = (
        (None, {
            'fields': ('title', 'icon', 'description', 'image', 'link')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
    )

    def move_up_down_links(self, obj):
        return format_html(
            '<a href="{}">↑</a> <a href="{}">↓</a>',
            f'../../../{obj._meta.app_label}/{obj._meta.model_name}/{obj.pk}/move-up/',
            f'../../../{obj._meta.app_label}/{obj._meta.model_name}/{obj.pk}/move-down/'
        )
    move_up_down_links.short_description = 'Reorder'


@admin.register(Statistic)
class StatisticAdmin(admin.ModelAdmin):
    list_display = ('label', 'number', 'icon', 'color_preview', 'order', 'is_active')
    list_filter = ('is_active', 'icon')
    list_editable = ('is_active',)
    ordering = ('order',)

    fieldsets = (
        (None, {
            'fields': ('icon', 'number', 'label', 'suffix')
        }),
        ('Styling', {
            'fields': ('color',)
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
    )

    def color_preview(self, obj):
        return format_html(
            '<span style="background-color: {}; width: 30px; height: 20px; display: inline-block; border: 1px solid #ccc;"></span> {}',
            obj.color, obj.color
        )
    color_preview.short_description = 'Color'


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'logo_preview', 'website', 'order', 'is_active')
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    search_fields = ('name', 'website')
    ordering = ('order',)

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="100" />', obj.logo.url)
        return '-'
    logo_preview.short_description = 'Logo'


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'order', 'is_active')
    list_filter = ('is_active', 'category')
    list_editable = ('is_active',)
    search_fields = ('question', 'answer')
    ordering = ('order',)

    fieldsets = (
        (None, {
            'fields': ('question', 'answer', 'category')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
    )


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'rating', 'image_preview', 'order', 'is_active', 'created_at')
    list_filter = ('is_active', 'rating')
    list_editable = ('is_active',)
    search_fields = ('name', 'role', 'content')
    ordering = ('order',)
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('name', 'role', 'content', 'image', 'rating')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 50%;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Photo'


class ContentBlockInline(admin.TabularInline):
    model = ContentBlock
    extra = 1
    fields = ('block_type', 'title', 'image', 'css_classes', 'is_active', 'order')
    ordering = ('order',)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'template', 'is_published', 'show_in_menu', 'menu_order', 'updated_at')
    list_filter = ('is_published', 'show_in_menu', 'template')
    list_editable = ('is_published', 'show_in_menu', 'menu_order')
    search_fields = ('title', 'content', 'meta_description')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    inlines = [ContentBlockInline]

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content')
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Display Settings', {
            'fields': ('template', 'is_published', 'show_in_menu', 'menu_order')
        }),
        ('Metadata', {
            'fields': ('author', 'published_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('message_preview', 'type', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active', 'type')
    list_editable = ('is_active',)
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('message', 'type')
        }),
        ('Link (Optional)', {
            'fields': ('link', 'link_text'),
            'classes': ('collapse',)
        }),
        ('Schedule', {
            'fields': ('is_active', 'start_date', 'end_date')
        }),
    )

    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ('platform', 'url', 'order', 'is_active')
    list_filter = ('is_active', 'platform')
    list_editable = ('is_active',)
    ordering = ('order',)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Site Information', {
            'fields': ('site_name', 'site_tagline', 'site_description')
        }),
        ('Header Settings', {
            'fields': ('logo', 'header_announcement', 'show_header_announcement'),
            'description': 'Configure header logo and announcement bar'
        }),
        ('Footer Settings', {
            'fields': (
                'footer_logo',
                'footer_about_title',
                'footer_about_text',
                'footer_contact_title',
                'copyright_text'
            ),
            'description': 'Customize footer content and branding'
        }),
        ('Primary Contact Information', {
            'fields': ('contact_email', 'contact_phone', 'contact_address', 'office_hours')
        }),
        ('Additional Contact Details', {
            'fields': ('alternate_email', 'alternate_phone', 'whatsapp_number'),
            'classes': ('collapse',)
        }),
        ('Social Media Links', {
            'fields': ('facebook_url', 'twitter_url', 'linkedin_url', 'instagram_url')
        }),
        ('Newsletter Settings', {
            'fields': ('newsletter_title', 'newsletter_description'),
            'classes': ('collapse',)
        }),
        ('Design & Branding', {
            'fields': ('primary_color', 'secondary_color', 'accent_color', 'favicon', 'default_og_image'),
            'classes': ('collapse',)
        }),
        ('Membership Settings', {
            'fields': ('membership_fee_regular', 'membership_fee_student', 'current_eltan_year'),
            'classes': ('collapse',)
        }),
        ('Payment Settings', {
            'fields': ('paystack_public_key', 'enable_online_payment'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Only allow one instance
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    list_editable = ('is_read',)
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'phone', 'subject', 'message', 'created_at')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False
@admin.register(HeroSlide)
class HeroSlideAdmin(OrderedModelAdmin):
    list_display = ('title', 'image_preview', 'order', 'is_active', 'created_at', 'move_up_down_links')
    list_filter = ('is_active', 'created_at')
    list_editable = ('is_active',)
    ordering = ('order',)

    fieldsets = (
        (None, {
            'fields': ('title', 'subtitle', 'image')
        }),
        ('CTA', {
            'fields': ('cta_text', 'cta_link')
        }),
        ('Display', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ('created_at', 'updated_at')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="120" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'

    # move_up_down_links is provided by OrderedModelAdmin
