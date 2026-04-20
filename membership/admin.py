from django.contrib import admin
#from  django_summernote.admin import SummernoteModelAdmin
from django.utils.html import format_html
from django.utils import timezone
from django.db import OperationalError as DBOperationalError
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpResponse
from openpyxl import Workbook
from datetime import datetime
from .models import Conference, ConferenceRegistration, EltanConference, EltanConferenceRegistration, ConferenceDocument, MemberProfile, MembershipType, Subscription, Sigs, SigsRegistration, Events, News, Resource, Download, ELTANYearSetting, Newsletter, ConferenceSpeaker, ConferenceSchedule, ConferenceSponsor, ConferenceLocMember, ExcoMember, SponsorshipPackage, ConferenceAccommodation



@admin.register(ELTANYearSetting)
class ELTANYearSettingAdmin(admin.ModelAdmin):
    list_display = ('eltan_year', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('eltan_year',)
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        # If making this setting active, deactivate all others
        if obj.is_active:
            ELTANYearSetting.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# class NewsAdmin(SummernoteModelAdmin):
#     summernote_fields = ('content',)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gender', 'phone_number', 'state', 'city']
    actions = ['export_to_excel']

    def export_to_excel(self, request, queryset):
        wb = Workbook()
        ws = wb.active
        ws.title = "Member Profiles"

        # Define headers
        headers = [
            'Full Name', 'Email', 'Gender', 'Phone Number', 'Address',
            'City', 'State', 'Country', 'Date of Birth', 'Created At'
        ]
        ws.append(headers)

        # Add data
        for obj in queryset:
            row = [
                f"{obj.user.first_name} {obj.user.last_name}",
                obj.user.email,
                obj.gender,
                obj.phone_number,
                obj.address,
                obj.city,
                obj.state,
                obj.country,
                obj.date_of_birth.strftime('%Y-%m-%d') if obj.date_of_birth else '',
                obj.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ]
            ws.append(row)

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=member_profiles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb.save(response)
        return response

    export_to_excel.short_description = "Export selected members to Excel"



class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_eltan_number', 'membership_type', 'start_date', 'end_date', 
                   'payment_status', 'amount_paid', 'payment_proof_thumbnail']
    actions = ['export_to_excel']
    
    # Add search fields
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'user__eltan_number', 
                     'membership_type', 'payment_status', 'state_chapter']
    
    # Add list filters
    list_filter = ['payment_status', 'membership_type', 'eltan_year', 'state_chapter']
    
    def get_eltan_number(self, obj):
        """Retrieve ELTAN Number from related CustomUser"""
        return obj.user.eltan_number
    get_eltan_number.short_description = 'ELTAN Number'
    
    def amount_paid(self, obj):
        """Display payment_amount as 'Amount Paid'"""
        return obj.payment_amount
    amount_paid.short_description = 'Amount Paid' 
    
    # Rest of the code remains unchanged
    def payment_proof_thumbnail(self, obj):
        if obj.payment_proof:
            return format_html(
                '<a href="#" onclick="showPaymentProof(\'{}\', event)" class="payment-proof-link">'
                '<img src="{}" style="max-height: 50px; border-radius: 4px; border: 1px solid #ddd;"/>'
                '</a>',
                obj.payment_proof.url,
                obj.payment_proof.url
            )
        return "No proof uploaded"
    payment_proof_thumbnail.short_description = 'Payment Proof'

    readonly_fields = ('payment_proof_full',)

    def payment_proof_full(self, obj):
        if obj.payment_proof:
            return format_html(
                '<div style="max-width: 100%; margin-top: 10px;">'
                '<img src="{}" style="max-width: 100%; max-height: 600px; border-radius: 8px;"/>'
                '</div>',
                obj.payment_proof.url
            )
        return "No proof uploaded"
    payment_proof_full.short_description = 'Payment Proof'

    def export_to_excel(self, request, queryset):
        wb = Workbook()
        ws = wb.active
        ws.title = "Subscriptions"
        headers = [
            'Member Name', 'Email', 'Eltan Number','Membership Type', 'Start Date',
            'End Date', 'Payment Status', 'Payment Amount', 'State Chapter'
        ]
        ws.append(headers)
        for obj in queryset:
            row = [
                f"{obj.user.first_name} {obj.user.last_name}",
                obj.user.email,
                obj.user.eltan_number,
                obj.membership_type,
                obj.start_date.strftime('%Y-%m-%d'),
                obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
                obj.payment_status,
                str(obj.payment_amount) if obj.payment_amount else '',
                obj.state_chapter
            ]
            ws.append(row)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=subscriptions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb.save(response)
        return response
    export_to_excel.short_description = "Export selected subscriptions to Excel"

    class Media:
        css = {
            'all': ('admin/css/payment_proof_modal.css',)
        }
        js = ('admin/js/payment_proof_modal.js',)



class ConferenceLocMemberInline(admin.StackedInline):
    model = ConferenceLocMember
    extra = 1
    fields = ('name', 'role', 'organization', 'email', 'phone', 'image', 'order')
    ordering = ('order', 'name')
    verbose_name = 'LOC Member'
    verbose_name_plural = 'Local Organizing Committee (LOC) Members'


class ConferenceSpeakerInline(admin.StackedInline):
    model = ConferenceSpeaker
    extra = 0
    fields = ('name', 'title', 'image', 'presentation_title', 'order')
    ordering = ('order', 'name')
    verbose_name = 'Speaker'
    verbose_name_plural = 'Speakers'


class ConferenceScheduleInline(admin.TabularInline):
    model = ConferenceSchedule
    extra = 0
    fields = ('date', 'start_time', 'end_time', 'session_title', 'location', 'speaker')


class ConferenceDocumentInline(admin.TabularInline):
    model = ConferenceDocument
    extra = 0
    fields = ('title', 'document', 'is_public')


class SponsorshipPackageInline(admin.StackedInline):
    model = SponsorshipPackage
    extra = 0
    fields = ('tier', 'tier_label', 'price_range', 'benefits', 'is_featured', 'cta_label', 'order')
    verbose_name = 'Sponsorship Package'
    verbose_name_plural = 'Sponsorship Packages'


class ConferenceAccommodationInline(admin.StackedInline):
    model = ConferenceAccommodation
    extra = 0
    fields = (
        'name', 'address', 'distance_from_venue', 'price_range', 'room_types',
        'contact_phone', 'contact_email', 'website', 'booking_deadline',
        'notes', 'is_recommended', 'image', 'order',
    )
    verbose_name = 'Accommodation'
    verbose_name_plural = 'Accommodation Options'


@admin.register(SponsorshipPackage)
class SponsorshipPackageAdmin(admin.ModelAdmin):
    list_display = ('tier_label', 'conference', 'price_range', 'is_featured', 'order')
    list_filter = ('conference', 'tier')
    ordering = ('conference', 'order')


@admin.register(ConferenceAccommodation)
class ConferenceAccommodationAdmin(admin.ModelAdmin):
    list_display = ('name', 'conference', 'distance_from_venue', 'price_range', 'is_recommended', 'order')
    list_filter = ('conference', 'is_recommended')
    search_fields = ('name', 'address')
    ordering = ('conference', 'order', 'name')


@admin.register(EltanConference)
class EltanConferenceAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'registration_status', 'is_active', 'member_fee', 'non_member_fee')
    readonly_fields = ('is_early_bird_active',)
    list_filter = ('is_active', 'start_date')
    search_fields = ('title', 'theme', 'description')
    actions = None
    inlines = [ConferenceLocMemberInline, ConferenceSpeakerInline, ConferenceScheduleInline, ConferenceDocumentInline, SponsorshipPackageInline, ConferenceAccommodationInline]
    fieldsets = (
        ('Conference Info', {
            'fields': ('title', 'theme', 'description', 'image', 'is_active')
        }),
        ('Dates & Venue', {
            'fields': ('start_date', 'end_date', 'venue')
        }),
        ('Registration', {
            'fields': ('registration_start', 'registration_end', 'early_bird_end', 'is_early_bird_active',
                       'abstract_form_link')
        }),
        ('Fees', {
            'fields': ('member_fee', 'member_early_bird_fee', 'non_member_fee', 'non_member_early_bird_fee',
                       'international_delegate_fee')
        }),
        ('Payment Links', {
            'fields': ('member_payment_link', 'non_member_payment_link'),
            'classes': ('collapse',),
        }),
        ('Contact', {
            'fields': ('contact_name', 'contact_email', 'contact_phone'),
        }),
        ('Content Tabs', {
            'fields': ('sub_themes', 'cfp_guidelines', 'sponsor_packages'),
            'description': 'These fields populate the Sub-Themes, Call for Papers, and Sponsors tabs on the conference portal.',
        }),
    )
    
    def get_queryset(self, request):
        """Avoid selecting newly added columns if migrations haven't been applied yet."""
        qs = super().get_queryset(request)
        try:
            # Force a lightweight evaluation to detect schema errors early
            list(qs.values_list('pk', flat=True)[:1])
            return qs.only(
                'id', 'title', 'theme', 'image', 'start_date', 'end_date', 'venue',
                'registration_start', 'registration_end', 'early_bird_end', 'is_active',
                'member_fee', 'member_early_bird_fee', 'non_member_fee', 'non_member_early_bird_fee',
                'international_delegate_fee', 'sponsor_packages'
            )
        except DBOperationalError:
            messages.error(request, 'Conference list is limited until database migrations are applied. Please run migrations to enable new fields.')
            return self.model.objects.none()

    def changelist_view(self, request, extra_context=None):
        try:
            return super().changelist_view(request, extra_context=extra_context)
        except DBOperationalError:
            messages.error(request, 'Conference list is unavailable until database migrations are applied for new fields.')
            from django.shortcuts import redirect
            return redirect('admin:index')

    def get_search_results(self, request, queryset, search_term):
        try:
            return super().get_search_results(request, queryset, search_term)
        except DBOperationalError:
            messages.error(request, 'Search disabled until database migrations are applied for conference fields.')
            return self.model.objects.none(), False
    
    def registration_status(self, obj):
        if obj.is_open_for_registration:
            return 'Open'
        elif timezone.now().date() < obj.registration_start:
            return 'Not Started'
        else:
            return 'Closed'
    registration_status.short_description = 'Registration Status'
    
    def save_model(self, request, obj, form, change):
        if not obj.member_fee or not obj.non_member_fee:
            raise ValidationError("All fee fields must be set")
        super().save_model(request, obj, form, change)


@admin.register(ConferenceLocMember)
class ConferenceLocMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'conference', 'order')
    list_filter = ('conference',)
    search_fields = ('name', 'role', 'organization', 'email', 'phone')
    ordering = ('conference', 'order', 'name')


class UserTypeFilter(admin.SimpleListFilter):
    title = 'User Type'  # Display name for the filter
    parameter_name = 'user_type'  # Query parameter name

    def lookups(self, request, model_admin):
        """
        Define filter options.
        """
        return (
            ('user', 'Authenticated User'),
            ('non_user', 'Non-User'),
        )

    def queryset(self, request, queryset):
        """
        Filter the queryset based on the selected option.
        """
        if self.value() == 'user':
            return queryset.filter(user__isnull=False)
        if self.value() == 'non_user':
            return queryset.filter(user__isnull=True)
        return queryset


@admin.register(EltanConferenceRegistration)
class EltanConferenceRegistrationAdmin(admin.ModelAdmin):
    list_display = ('display_user', 'conference', 'registration_type', 'payment_status', 'amount_paid', 
                    'is_presenting', 'registered_at', 'phone')
    list_filter = (UserTypeFilter, 'conference', 'registration_type', 'payment_status', 'is_presenting')
    
    def display_user(self, obj):
        """
        Custom method to display user or non-user details.
        """
        if obj.user:
            return obj.user  # Display the authenticated user
        else:
            # Display non-user details
            return f"{obj.first_name} {obj.last_name} ({obj.email})"
    
    display_user.short_description = 'Member / Non-Member'
    
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 
                    'paper_title', 'email', 'first_name', 'last_name')  # Added non-user fields
    readonly_fields = ('registered_at',)
    
    actions = ['export_registrations']
    
    def export_registrations(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="conference_registrations.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Email', 'Registration Type', 'Payment Status',
            'Amount Paid', 'Is Presenting', 'Paper Title', 'Phone',
            'Registration Date'
        ])
        
        for registration in queryset:
            # Get name and email based on whether it's a member or non-member
            if registration.user:
                name = f"{registration.user.first_name} {registration.user.last_name}"
                email = registration.user.email
            else:
                name = f"{registration.first_name} {registration.last_name}"
                email = registration.email
            
            writer.writerow([
                name,
                email,
                registration.registration_type,
                registration.payment_status,
                registration.amount_paid,
                'Yes' if registration.is_presenting else 'No',
                registration.paper_title or '',
                registration.phone or '',
                registration.registered_at.strftime('%Y-%m-%d %H:%M:%S') if registration.registered_at else ''
            ])
        
        return response
    export_registrations.short_description = "Export selected registrations to CSV"

@admin.register(ConferenceDocument)
class ConferenceDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'conference', 'is_public', 'uploaded_at')
    list_filter = ('conference', 'is_public')
    search_fields = ('title',)


@admin.register(ConferenceSpeaker)
class ConferenceSpeakerAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'conference', 'presentation_title')
    list_filter = ('conference',)
    search_fields = ('name', 'title', 'presentation_title')
    ordering = ('conference', 'order', 'name')


@admin.register(ConferenceSchedule)
class ConferenceScheduleAdmin(admin.ModelAdmin):
    list_display = ('session_title', 'conference', 'date', 'start_time', 'end_time', 'location', 'speaker')
    list_filter = ('conference', 'date')
    search_fields = ('session_title', 'location', 'speaker__name')
    ordering = ('date', 'start_time')


@admin.register(ConferenceSponsor)
class ConferenceSponsorAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'conference', 'level', 'contact_name', 'is_approved')
    list_filter = ('conference', 'level', 'is_approved')
    search_fields = ('company_name', 'contact_name', 'contact_email')
    list_editable = ('is_approved',)


@admin.register(ExcoMember)
class ExcoMemberAdmin(admin.ModelAdmin):
    list_display = (
        'photo_preview',
        'full_name',
        'position',
        'institution',
        'tenure_period',
        'status_badge',
        'order'
    )

    list_filter = (
        'is_active',
        'is_archived',
        'position',
        'start_date',
    )

    search_fields = (
        'full_name',
        'position',
        'institution',
        'email',
        'user__first_name',
        'user__last_name',
        'user__email',
    )

    list_editable = ('order',)

    ordering = ('is_archived', '-is_active', 'order', 'position')

    actions = ['archive_members', 'unarchive_members', 'mark_as_active', 'export_to_excel']

    autocomplete_fields = ['user']

    readonly_fields = ('created_at', 'updated_at', 'photo_preview_large')

    fieldsets = (
        ('Member Information', {
            'fields': (
                'user',
                'full_name',
                'position',
                'institution',
            )
        }),
        ('Contact Details', {
            'fields': (
                'email',
                'phone',
                'linkedin_url',
            )
        }),
        ('Photo & Bio', {
            'fields': (
                'photo',
                'photo_preview_large',
                'bio',
            )
        }),
        ('Tenure & Status', {
            'fields': (
                'start_date',
                'end_date',
                'is_active',
                'is_archived',
                'order',
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def photo_preview(self, obj):
        """Small thumbnail for list view"""
        photo_url = obj.get_photo_url()
        if photo_url:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%; object-fit: cover; border: 2px solid #ddd;"/>',
                photo_url
            )
        return format_html(
            '<div style="width: 50px; height: 50px; border-radius: 50%; background: #e0e0e0; '
            'display: flex; align-items: center; justify-content: center; color: #666; font-size: 20px;">{}</div>',
            obj.full_name[0] if obj.full_name else '?'
        )
    photo_preview.short_description = 'Photo'

    def photo_preview_large(self, obj):
        """Large preview for detail view"""
        photo_url = obj.get_photo_url()
        if photo_url:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px; border-radius: 8px; border: 1px solid #ddd;"/>',
                photo_url
            )
        return "No photo uploaded"
    photo_preview_large.short_description = 'Photo Preview'

    def tenure_period(self, obj):
        """Display tenure as a date range"""
        start = obj.start_date.strftime('%b %Y')
        if obj.end_date:
            end = obj.end_date.strftime('%b %Y')
            return f"{start} - {end}"
        return f"{start} - Present"
    tenure_period.short_description = 'Tenure'

    def status_badge(self, obj):
        """Visual status indicator"""
        if obj.is_archived:
            return format_html(
                '<span style="background: #9e9e9e; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: 600;">ARCHIVED</span>'
            )
        elif obj.is_active:
            return format_html(
                '<span style="background: #4caf50; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: 600;">CURRENT</span>'
            )
        else:
            return format_html(
                '<span style="background: #ff9800; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: 600;">INACTIVE</span>'
            )
    status_badge.short_description = 'Status'

    def archive_members(self, request, queryset):
        """Archive selected members (move to Past Exco)"""
        updated = queryset.update(is_archived=True, is_active=False)
        self.message_user(
            request,
            f'{updated} member(s) successfully archived and moved to Past Exco.',
            messages.SUCCESS
        )
    archive_members.short_description = "Archive selected members (move to Past Exco)"

    def unarchive_members(self, request, queryset):
        """Unarchive selected members"""
        updated = queryset.update(is_archived=False)
        self.message_user(
            request,
            f'{updated} member(s) unarchived. Remember to set is_active if they should appear in Current Exco.',
            messages.WARNING
        )
    unarchive_members.short_description = "Unarchive selected members"

    def mark_as_active(self, request, queryset):
        """Mark as active (current exco)"""
        updated = queryset.update(is_active=True, is_archived=False)
        self.message_user(
            request,
            f'{updated} member(s) marked as active in Current Exco.',
            messages.SUCCESS
        )
    mark_as_active.short_description = "Mark as active (Current Exco)"

    def export_to_excel(self, request, queryset):
        """Export to Excel following existing pattern"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Exco Members"

        headers = [
            'Full Name', 'Position', 'Institution', 'Email', 'Phone',
            'LinkedIn', 'Start Date', 'End Date', 'Status', 'Is Active', 'Is Archived'
        ]
        ws.append(headers)

        for obj in queryset:
            row = [
                obj.full_name,
                obj.get_position_display(),
                obj.institution,
                obj.get_email(),
                obj.phone,
                obj.linkedin_url,
                obj.start_date.strftime('%Y-%m-%d'),
                obj.end_date.strftime('%Y-%m-%d') if obj.end_date else 'Present',
                'Archived' if obj.is_archived else ('Active' if obj.is_active else 'Inactive'),
                'Yes' if obj.is_active else 'No',
                'Yes' if obj.is_archived else 'No',
            ]
            ws.append(row)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=exco_members_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb.save(response)
        return response
    export_to_excel.short_description = "Export selected members to Excel"

    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related('user').prefetch_related('user__memberprofile')


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('title', 'month_year', 'file_size', 'upload_date', 'is_published', 'is_featured')
    list_filter = ('year', 'month', 'is_published', 'is_featured')
    search_fields = ('title', 'description')
    ordering = ('-year', '-month')
    list_editable = ('is_published', 'is_featured')
    readonly_fields = ('upload_date', 'file_size')

    fieldsets = (
        ('Newsletter Information', {
            'fields': ('title', 'month', 'year', 'description')
        }),
        ('Files', {
            'fields': ('pdf_file', 'thumbnail'),
            'description': 'Upload the newsletter PDF file and an optional thumbnail image.'
        }),
        ('Publication Settings', {
            'fields': ('is_published', 'is_featured', 'upload_date', 'file_size'),
            'classes': ('collapse',)
        }),
    )

    def month_year(self, obj):
        return f"{obj.get_month_display()} {obj.year}"
    month_year.short_description = "Period"

    def save_model(self, request, obj, form, change):
        """Provide helpful feedback when saving"""
        super().save_model(request, obj, form, change)
        if not change:  # New newsletter
            self.message_user(request, f"Newsletter '{obj.title}' uploaded successfully!", messages.SUCCESS)
        else:
            self.message_user(request, f"Newsletter '{obj.title}' updated successfully!", messages.SUCCESS)



# Register your models here.
admin.site.register(MemberProfile, MemberProfileAdmin)
#admin.site.register(Conference)
#admin.site.register(ConferenceRegistration, ConferenceRegistrationAdmin)
admin.site.register(MembershipType)
admin.site.register(Subscription, SubscriptionAdmin)
# SIG Admin with inline members
class SigsRegistrationInline(admin.TabularInline):
    model = SigsRegistration
    extra = 0
    fields = ['user', 'registration_date']
    readonly_fields = ['registration_date']
    autocomplete_fields = ['user']

class SigsAdmin(admin.ModelAdmin):
    list_display = ['title', 'moderator', 'member_count', 'is_active', 'is_featured', 'order']
    list_filter = ['is_active', 'is_featured']
    search_fields = ['title', 'description']
    list_editable = ['is_active', 'is_featured', 'order']
    inlines = [SigsRegistrationInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'image', 'icon')
        }),
        ('Moderation', {
            'fields': ('moderator',)
        }),
        ('Display Settings', {
            'fields': ('is_active', 'is_featured', 'order')
        }),
    )

    def member_count(self, obj):
        return obj.member_count
    member_count.short_description = 'Members'

# SIG Registration Admin
class SigsRegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'sig', 'registration_date']
    list_filter = ['sig', 'registration_date']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'sig__title']
    date_hierarchy = 'registration_date'

admin.site.register(Sigs, SigsAdmin)
admin.site.register(SigsRegistration, SigsRegistrationAdmin)
admin.site.register(Events)
admin.site.register(News)
admin.site.register(Resource)
admin.site.register(Download)


admin.site.site_header = "ELTAN - Dashboard Admin"
admin.site.site_title ="ELTAN ADMIN"
