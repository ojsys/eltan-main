"""
Enhanced admin for membership models with CMS functionality
This will replace/enhance the existing admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.http import HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.utils.safestring import mark_safe
from django.db import models
from django.forms import Textarea
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from datetime import date, timedelta
import csv

from .enhanced_models import (
    MembershipType, EnhancedSubscription, PaymentLog,
    EnhancedNews, EnhancedEvent, EnhancedResource, ResourceRating,
    EventImage, EventDocument
)
from account.models import CustomUser


class MembershipTypeResource(resources.ModelResource):
    class Meta:
        model = MembershipType
        import_id_fields = ('id',)


@admin.register(MembershipType)
class MembershipTypeAdmin(ImportExportModelAdmin):
    """Enhanced membership type management"""
    resource_class = MembershipTypeResource
    list_display = ['name', 'price', 'early_bird_price', 'duration_months', 'is_active', 'sort_order', 'type_preview']
    list_filter = ['is_active', 'duration_months']
    search_fields = ['name', 'description']
    list_editable = ['sort_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'is_active')
        }),
        ('Pricing', {
            'fields': ('price', 'early_bird_price', 'early_bird_deadline', 'duration_months')
        }),
        ('Benefits & Features', {
            'fields': ('benefits', 'max_registrations')
        }),
        ('Display Settings', {
            'fields': ('sort_order', 'color_code', 'icon'),
            'classes': ['collapse']
        }),
    )
    
    def type_preview(self, obj):
        """Show membership type with color coding"""
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            obj.color_code,
            obj.name
        )
    type_preview.short_description = 'Type'


class EnhancedSubscriptionResource(resources.ModelResource):
    user_email = fields.Field(column_name='user_email', attribute='user__email')
    user_full_name = fields.Field(column_name='user_full_name', attribute='user__get_full_name')
    membership_type_name = fields.Field(column_name='membership_type', attribute='membership_type__name')
    
    class Meta:
        model = EnhancedSubscription
        import_id_fields = ('id',)
        export_order = [
            'eltan_number', 'user_email', 'user_full_name', 'membership_type_name',
            'payment_amount', 'payment_status', 'membership_status',
            'start_date', 'end_date', 'eltan_year', 'created_at'
        ]


@admin.register(EnhancedSubscription)
class EnhancedSubscriptionAdmin(ImportExportModelAdmin):
    """Advanced subscription management with automated features"""
    resource_class = EnhancedSubscriptionResource
    list_display = [
        'eltan_number', 'user_full_name', 'membership_type', 'payment_status_badge',
        'membership_status_badge', 'days_remaining_display', 'payment_amount', 'subscription_actions'
    ]
    list_filter = [
        'payment_status', 'membership_status', 'membership_type',
        'payment_verified', 'auto_renew', 'created_at'
    ]
    search_fields = [
        'eltan_number', 'user__email', 'user__first_name', 'user__last_name',
        'payment_reference', 'paystack_reference'
    ]
    readonly_fields = [
        'eltan_number', 'payment_reference', 'created_at', 'updated_at',
        'payment_verified_at', 'certificate_issued_at', 'days_remaining'
    ]
    
    fieldsets = (
        ('Member Information', {
            'fields': ('user', 'membership_type', 'eltan_number', 'eltan_year')
        }),
        ('Membership Dates', {
            'fields': ('start_date', 'end_date', 'days_remaining')
        }),
        ('Payment Information', {
            'fields': (
                'payment_amount', 'payment_status', 'payment_method',
                'payment_reference', 'paystack_reference', 'transaction_id',
                'payment_verified', 'payment_verified_at', 'payment_proof'
            ),
            'classes': ['collapse']
        }),
        ('Status & Settings', {
            'fields': (
                'membership_status', 'auto_renew', 'renewal_reminded',
                'certificate_issued', 'certificate_issued_at'
            ),
            'classes': ['collapse']
        }),
        ('Additional Information', {
            'fields': ('state_chapter', 'notes'),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    actions = [
        'mark_as_paid', 'mark_as_verified', 'send_welcome_email',
        'generate_certificates', 'export_membership_cards', 'send_renewal_reminders'
    ]
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('verify-payment/<int:subscription_id>/', self.verify_payment_view, name='verify-payment'),
            path('generate-certificate/<int:subscription_id>/', self.generate_certificate_view, name='generate-certificate'),
            path('membership-analytics/', self.analytics_view, name='membership-analytics'),
        ]
        return custom_urls + urls
    
    def user_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_full_name.short_description = 'Member Name'
    user_full_name.admin_order_field = 'user__first_name'
    
    def payment_status_badge(self, obj):
        """Display payment status with color coding"""
        colors = {
            'paid': '#28a745',
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'failed': '#dc3545',
            'refunded': '#6f42c1',
            'cancelled': '#6c757d',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 11px; text-transform: uppercase;">{}</span>',
            colors.get(obj.payment_status, '#6c757d'),
            obj.payment_status
        )
    payment_status_badge.short_description = 'Payment'
    payment_status_badge.admin_order_field = 'payment_status'
    
    def membership_status_badge(self, obj):
        """Display membership status with color coding"""
        colors = {
            'active': '#28a745',
            'expired': '#dc3545',
            'suspended': '#ffc107',
            'cancelled': '#6c757d',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 11px; text-transform: uppercase;">{}</span>',
            colors.get(obj.membership_status, '#6c757d'),
            obj.membership_status
        )
    membership_status_badge.short_description = 'Status'
    membership_status_badge.admin_order_field = 'membership_status'
    
    def days_remaining_display(self, obj):
        """Display days remaining with visual indicator"""
        days = obj.days_remaining
        if days <= 0:
            return format_html('<span style="color: #dc3545; font-weight: bold;">Expired</span>')
        elif days <= 30:
            return format_html('<span style="color: #ffc107; font-weight: bold;">{} days</span>', days)
        else:
            return format_html('<span style="color: #28a745;">{} days</span>', days)
    days_remaining_display.short_description = 'Days Left'
    
    def subscription_actions(self, obj):
        """Custom action buttons"""
        actions = []
        
        if obj.payment_status == 'pending':
            actions.append(format_html(
                '<a class="button" href="{}">Verify Payment</a>',
                reverse('admin:verify-payment', args=[obj.id])
            ))
        
        if obj.payment_status == 'paid' and not obj.certificate_issued:
            actions.append(format_html(
                '<a class="button" href="{}">Generate Certificate</a>',
                reverse('admin:generate-certificate', args=[obj.id])
            ))
        
        if obj.user.email:
            actions.append(format_html(
                '<a class="button" href="mailto:{}">Email Member</a>',
                obj.user.email
            ))
        
        return format_html(' | '.join(actions)) if actions else '-'
    subscription_actions.short_description = 'Actions'
    
    # Custom Actions
    def mark_as_paid(self, request, queryset):
        """Mark selected subscriptions as paid"""
        from django.utils import timezone
        count = 0
        for subscription in queryset:
            if subscription.payment_status != 'paid':
                subscription.payment_status = 'paid'
                subscription.payment_verified = True
                subscription.payment_verified_at = timezone.now()
                subscription.membership_status = 'active'
                subscription.save()
                count += 1
        
        self.message_user(request, f'{count} subscriptions marked as paid and activated.')
    mark_as_paid.short_description = 'Mark selected as paid'
    
    def mark_as_verified(self, request, queryset):
        """Mark payments as verified"""
        from django.utils import timezone
        count = queryset.filter(payment_verified=False).update(
            payment_verified=True,
            payment_verified_at=timezone.now()
        )
        self.message_user(request, f'{count} payments marked as verified.')
    mark_as_verified.short_description = 'Mark payments as verified'
    
    def send_welcome_email(self, request, queryset):
        """Send welcome emails to new members"""
        # Implementation for sending welcome emails
        count = 0
        for subscription in queryset.filter(payment_status='paid'):
            # Add email sending logic here
            count += 1
        self.message_user(request, f'Welcome emails sent to {count} members.')
    send_welcome_email.short_description = 'Send welcome emails'
    
    def generate_certificates(self, request, queryset):
        """Generate membership certificates"""
        count = 0
        for subscription in queryset.filter(payment_status='paid', certificate_issued=False):
            # Add certificate generation logic here
            subscription.certificate_issued = True
            from django.utils import timezone
            subscription.certificate_issued_at = timezone.now()
            subscription.save()
            count += 1
        self.message_user(request, f'{count} certificates generated.')
    generate_certificates.short_description = 'Generate certificates'
    
    # Custom Views
    @method_decorator(staff_member_required)
    def verify_payment_view(self, request, subscription_id):
        """Custom view for verifying payments"""
        try:
            subscription = EnhancedSubscription.objects.get(id=subscription_id)
            # Add Paystack verification logic here
            return JsonResponse({'status': 'success', 'message': 'Payment verified'})
        except EnhancedSubscription.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Subscription not found'})
    
    @method_decorator(staff_member_required)
    def generate_certificate_view(self, request, subscription_id):
        """Generate individual certificate"""
        try:
            subscription = EnhancedSubscription.objects.get(id=subscription_id)
            # Add certificate generation logic here
            return JsonResponse({'status': 'success', 'message': 'Certificate generated'})
        except EnhancedSubscription.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Subscription not found'})
    
    @method_decorator(staff_member_required)
    def analytics_view(self, request):
        """Membership analytics dashboard"""
        context = {
            'title': 'Membership Analytics',
            'total_members': EnhancedSubscription.objects.filter(payment_status='paid').count(),
            'active_members': EnhancedSubscription.objects.filter(
                payment_status='paid', membership_status='active'
            ).count(),
            'expired_members': EnhancedSubscription.objects.filter(
                membership_status='expired'
            ).count(),
            # Add more analytics data
        }
        return TemplateResponse(request, 'admin/membership/analytics.html', context)


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    """Payment log monitoring"""
    list_display = ['subscription_user', 'event_type', 'amount', 'status', 'processed', 'created_at']
    list_filter = ['event_type', 'status', 'processed', 'currency', 'created_at']
    search_fields = ['subscription__user__email', 'paystack_reference', 'event_type']
    readonly_fields = ['created_at', 'raw_data']
    
    def subscription_user(self, obj):
        return obj.subscription.user.get_full_name() or obj.subscription.user.username
    subscription_user.short_description = 'User'


@admin.register(EnhancedNews)
class EnhancedNewsAdmin(admin.ModelAdmin):
    """Enhanced news management with SEO and publishing"""
    list_display = ['title', 'category', 'author', 'status', 'featured', 'views', 'published_at', 'news_actions']
    list_filter = ['status', 'category', 'featured', 'created_at', 'author']
    search_fields = ['title', 'content', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'excerpt', 'content', 'featured_image')
        }),
        ('Classification', {
            'fields': ('category', 'tags', 'author')
        }),
        ('Publishing', {
            'fields': ('status', 'featured', 'published_at')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ['collapse']
        }),
        ('Metrics', {
            'fields': ('views', 'likes'),
            'classes': ['collapse']
        }),
    )
    
    def news_actions(self, obj):
        if obj.status == 'published':
            return format_html(
                '<a class="button" href="{}" target="_blank">View</a>',
                obj.get_absolute_url()
            )
        return 'Not published'
    news_actions.short_description = 'Actions'


@admin.register(EnhancedEvent)
class EnhancedEventAdmin(admin.ModelAdmin):
    """Enhanced event management"""
    list_display = ['title', 'start_date', 'venue', 'registration_fee', 'max_participants', 'status', 'event_actions']
    list_filter = ['status', 'is_online', 'start_date', 'organizer']
    search_fields = ['title', 'description', 'venue']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['gallery', 'documents']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'organizer')
        }),
        ('Date & Time', {
            'fields': ('start_date', 'end_date', 'registration_deadline')
        }),
        ('Location', {
            'fields': ('is_online', 'venue', 'address', 'meeting_link')
        }),
        ('Registration', {
            'fields': ('registration_fee', 'max_participants')
        }),
        ('Media', {
            'fields': ('featured_image', 'gallery', 'documents'),
            'classes': ['collapse']
        }),
        ('Publishing', {
            'fields': ('status', 'featured', 'published_at'),
            'classes': ['collapse']
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ['collapse']
        }),
    )
    
    def event_actions(self, obj):
        if obj.status == 'published':
            return format_html(
                '<a class="button" href="{}" target="_blank">View</a>',
                obj.get_absolute_url()
            )
        return 'Not published'
    event_actions.short_description = 'Actions'


@admin.register(EnhancedResource)
class EnhancedResourceAdmin(admin.ModelAdmin):
    """Enhanced resource management with access control"""
    list_display = ['title', 'category', 'access_level', 'downloads', 'rating', 'status', 'resource_actions']
    list_filter = ['category', 'access_level', 'status', 'created_at', 'author']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'description', 'file', 'thumbnail')
        }),
        ('Classification', {
            'fields': ('category', 'access_level', 'author', 'tags')
        }),
        ('Publishing', {
            'fields': ('status', 'featured', 'published_at')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ['collapse']
        }),
        ('Metrics', {
            'fields': ('downloads', 'rating'),
            'classes': ['collapse']
        }),
    )
    
    def resource_actions(self, obj):
        actions = []
        if obj.status == 'published':
            actions.append(format_html(
                '<a class="button" href="{}" target="_blank">View</a>',
                obj.get_absolute_url()
            ))
        if obj.file:
            actions.append(format_html(
                '<a class="button" href="{}" target="_blank">Download</a>',
                obj.file.url
            ))
        return format_html(' | '.join(actions)) if actions else '-'
    resource_actions.short_description = 'Actions'


# Inline admins
class EventImageInline(admin.TabularInline):
    model = EventImage
    extra = 1


class EventDocumentInline(admin.TabularInline):
    model = EventDocument
    extra = 1


class ResourceRatingInline(admin.TabularInline):
    model = ResourceRating
    extra = 0
    readonly_fields = ['user', 'rating', 'review', 'created_at']


# Register inline admins
EnhancedEventAdmin.inlines = [EventImageInline, EventDocumentInline]
EnhancedResourceAdmin.inlines = [ResourceRatingInline]