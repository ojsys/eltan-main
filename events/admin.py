import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from membership.models import Events

from . import services
from .models import (
    EventAnswer,
    EventCertificate,
    EventQuestion,
    EventRegistration,
    EventResponse,
    EventSetup,
)


class EventSetupInline(admin.StackedInline):
    model = EventSetup
    can_delete = False
    extra = 0
    max_num = 1
    fieldsets = (
        ('Registration', {'fields': (
            'accepts_registrations', 'starts_at', 'registration_closes_at',
            ('member_fee', 'guest_fee'), 'join_link', 'joining_instructions',
        )}),
        ('Post-event activity', {
            'description': 'Open the activity during or after the session and announce the attendance code live.',
            'fields': ('activity_is_open', 'activity_closes_at', 'attendance_code', 'activity_intro'),
        }),
        ('Certificate', {'fields': (
            'issues_certificates', 'certificate_title', 'cpd_hours', 'certificate_template',
            ('certificate_name_x', 'certificate_name_baseline'),
            ('certificate_name_max_width', 'certificate_name_font_size'),
        )}),
    )


class EventQuestionInline(admin.TabularInline):
    model = EventQuestion
    extra = 0
    fields = ('order', 'prompt', 'kind', 'choices', 'required')
    verbose_name = 'Activity question'
    verbose_name_plural = (
        'Activity questions — three defaults are added when registration is first set up; edit them freely'
    )


admin.site.unregister(Events)


@admin.register(Events)
class EventsAdmin(admin.ModelAdmin):
    list_display = ('event_title', 'event_date', 'event_location', 'is_published',
                    'takes_registrations', 'confirmed_registrations', 'certificates_issued')
    list_filter = ('is_published',)
    search_fields = ('event_title', 'event_location')
    inlines = [EventSetupInline, EventQuestionInline]

    @admin.display(boolean=True, description='Registers here')
    def takes_registrations(self, obj):
        setup = getattr(obj, 'setup', None)
        return bool(setup and setup.accepts_registrations)

    @admin.display(description='Confirmed')
    def confirmed_registrations(self, obj):
        count = obj.registrations.filter(status=EventRegistration.CONFIRMED).count()
        url = reverse('admin:events_eventregistration_changelist') + f'?event__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description='Certificates')
    def certificates_issued(self, obj):
        return EventCertificate.objects.filter(registration__event=obj).count()


class EventAnswerInline(admin.TabularInline):
    model = EventAnswer
    extra = 0
    fields = ('prompt', 'answer')
    readonly_fields = ('prompt', 'answer')
    can_delete = False


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'event', 'is_member', 'amount', 'status', 'ticket_id',
                    'activity_done', 'confirmation_ok', 'created_at')
    list_filter = ('status', 'is_member', 'event')
    search_fields = ('first_name', 'last_name', 'email', 'ticket_id', 'payment_reference', 'paystack_reference')
    readonly_fields = ('payment_reference', 'paystack_reference', 'paid_at', 'confirmed_at', 'ticket_id',
                       'confirmation_sent_at', 'confirmation_error', 'created_at', 'registration_link')
    raw_id_fields = ('user',)
    actions = ['confirm_manually', 'resend_confirmation', 'send_activity_invitation',
               'export_responses', 'reset_code_attempts']

    @admin.display(boolean=True, description='Activity')
    def activity_done(self, obj):
        return obj.has_completed_activity

    @admin.display(boolean=True, description='Ticket emailed')
    def confirmation_ok(self, obj):
        if not obj.is_confirmed:
            return None
        return bool(obj.confirmation_sent_at)

    @admin.display(description="Attendee's page")
    def registration_link(self, obj):
        if not obj.pk:
            return '—'
        return format_html('<a href="{}" target="_blank">{}</a>', obj.get_absolute_url(), 'Open')

    @admin.action(description='Confirm selected (payment received another way) and email tickets')
    def confirm_manually(self, request, queryset):
        done = 0
        for registration in queryset.filter(status=EventRegistration.PENDING):
            if registration.confirm():
                services.send_confirmation(registration)
                done += 1
        self.message_user(request, f'{done} registration(s) confirmed.', messages.SUCCESS)

    @admin.action(description='Resend ticket email')
    def resend_confirmation(self, request, queryset):
        sent = failed = 0
        for registration in queryset.filter(status=EventRegistration.CONFIRMED):
            ok, _ = services.send_confirmation(registration)
            sent, failed = sent + ok, failed + (not ok)
        self.message_user(
            request, f'{sent} sent' + (f', {failed} failed (see each registration)' if failed else '') + '.',
            messages.SUCCESS if not failed else messages.WARNING,
        )

    @admin.action(description='Email the post-event activity link (to those who have not done it)')
    def send_activity_invitation(self, request, queryset):
        sent = failed = skipped = 0
        for registration in queryset.filter(status=EventRegistration.CONFIRMED).select_related('event__setup'):
            if registration.has_completed_activity or not registration.event.setup.activity_available:
                skipped += 1
                continue
            ok, _ = services.send_activity_invitation(registration)
            sent, failed = sent + ok, failed + (not ok)
        self.message_user(
            request,
            f'{sent} invitation(s) sent, {failed} failed, {skipped} skipped '
            '(already done, or the activity is not open).',
            messages.SUCCESS if not failed else messages.WARNING,
        )

    @admin.action(description='Export activity responses (CSV)')
    def export_responses(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="event-responses.csv"'
        writer = csv.writer(response)
        writer.writerow(['Event', 'Name', 'Email', 'Ticket ID', 'Member', 'Submitted',
                         'Certificate ID', 'Question', 'Answer'])
        rows = (
            EventResponse.objects.filter(registration__in=queryset)
            .select_related('registration__event', 'registration__certificate')
            .prefetch_related('answers')
        )
        for item in rows:
            registration = item.registration
            certificate = getattr(registration, 'certificate', None)
            base = [registration.event.event_title, registration.full_name, registration.email,
                    registration.ticket_id, 'yes' if registration.is_member else 'no',
                    item.submitted_at.strftime('%Y-%m-%d %H:%M'),
                    certificate.certificate_id if certificate else '']
            for answer in item.answers.all():
                writer.writerow(base + [answer.prompt, answer.answer])
        return response

    @admin.action(description='Allow more attendance-code attempts')
    def reset_code_attempts(self, request, queryset):
        count = queryset.update(failed_code_attempts=0)
        self.message_user(request, f'{count} registration(s) reset.', messages.SUCCESS)


@admin.register(EventResponse)
class EventResponseAdmin(admin.ModelAdmin):
    list_display = ('registration', 'submitted_at')
    list_filter = ('registration__event',)
    search_fields = ('registration__first_name', 'registration__last_name', 'registration__email')
    readonly_fields = ('registration', 'submitted_at', 'code_entered')
    inlines = [EventAnswerInline]

    def has_add_permission(self, request):
        return False


@admin.register(EventCertificate)
class EventCertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_id', 'participant_name', 'event_title', 'issued_at',
                    'download_count', 'is_revoked')
    list_filter = ('is_revoked', 'registration__event')
    search_fields = ('certificate_id', 'participant_name', 'registration__email')
    readonly_fields = ('registration', 'certificate_id', 'participant_name', 'event_title',
                       'certificate_title', 'cpd_hours', 'issued_at', 'download_count', 'last_downloaded_at')

    def has_add_permission(self, request):
        return False
