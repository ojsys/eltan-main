"""Admin for JELTAN.

The editorial work — decisions, invitations, publishing — is done in the editor
UI, where the workflow rules are enforced. What lives here is the configuration
and the corrections: journal front matter, sections, the board, editor roles, and
a read-mostly view of manuscripts for when someone needs to look at the record.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Article,
    ArticleAuthor,
    EditorialBoardMember,
    EditorialDecision,
    Issue,
    JournalRole,
    JournalSettings,
    Proof,
    ReviewAssignment,
    ScreeningReport,
    Section,
    Submission,
    SubmissionAuthor,
    SubmissionEvent,
    SubmissionFile,
)


@admin.register(JournalSettings)
class JournalSettingsAdmin(admin.ModelAdmin):
    """One row of journal-wide configuration and front matter."""

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'short_name', 'tagline', 'publisher', 'issn_online', 'issn_print', 'cover_image'),
        }),
        ('Front matter', {
            'fields': (
                'aims_and_scope', 'author_guidelines', 'peer_review_policy',
                'publication_ethics', 'open_access_policy', 'copyright_notice',
            ),
            'description': 'These are the pages readers and authors see on the public JELTAN site.',
        }),
        ('Article processing charge', {
            'fields': ('apc_amount', 'apc_currency'),
            'description': 'Charged to the corresponding author on acceptance. Set the amount to 0 to waive it for everyone.',
        }),
        ('Peer review', {
            'fields': ('review_days', 'reviews_required'),
        }),
        ('Submissions', {
            'fields': ('is_accepting_submissions', 'closed_message', 'contact_email'),
        }),
    )

    readonly_fields = ('portal_link',)

    def get_fieldsets(self, request, obj=None):
        return (
            ('Editorial portal', {
                'fields': ('portal_link',),
                'description': (
                    'Decisions, the editorial queue and the record of what this '
                    'journal has published are worked in the portal, not here — '
                    'that is where the workflow rules and the author emails live.'
                ),
            }),
        ) + self.fieldsets

    def portal_link(self, obj=None):
        return format_html(
            '<a class="button" href="{}" target="_blank">Open the editorial portal</a>',
            reverse('journal:editor_portal'),
        )
    portal_link.short_description = 'Portal'

    def has_add_permission(self, request):
        # A second settings row would silently take effect or be ignored
        # depending on ordering; neither is a good surprise.
        return not JournalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JournalRole)
class JournalRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)


@admin.register(EditorialBoardMember)
class EditorialBoardMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'affiliation', 'country', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    list_filter = ('is_active', 'country')
    search_fields = ('name', 'position', 'affiliation')


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'peer_reviewed', 'is_active', 'order')
    list_editable = ('peer_reviewed', 'is_active', 'order')
    prepopulated_fields = {'slug': ('name',)}


class SubmissionAuthorInline(admin.TabularInline):
    model = SubmissionAuthor
    extra = 0


class SubmissionFileInline(admin.TabularInline):
    model = SubmissionFile
    extra = 0
    readonly_fields = ('uploaded_at', 'uploaded_by', 'original_name')


class ReviewAssignmentInline(admin.TabularInline):
    model = ReviewAssignment
    extra = 0
    fields = ('reviewer_name', 'reviewer_email', 'round', 'status', 'recommendation', 'due_date')
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class EditorialDecisionInline(admin.TabularInline):
    model = EditorialDecision
    extra = 0
    readonly_fields = ('decision', 'editor', 'round', 'decided_at', 'letter_to_author')

    def has_add_permission(self, request, obj=None):
        return False


class ScreeningReportInline(admin.TabularInline):
    model = ScreeningReport
    extra = 0
    readonly_fields = ('passed', 'screened_by', 'screened_at', 'notes_to_author', 'internal_notes')
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


class ProofInline(admin.TabularInline):
    model = Proof
    extra = 0
    readonly_fields = ('version', 'status', 'sent_by', 'sent_at', 'responded_at', 'corrections')
    fields = readonly_fields + ('file', 'due_date')

    def has_add_permission(self, request, obj=None):
        return False


class SubmissionEventInline(admin.TabularInline):
    model = SubmissionEvent
    extra = 0
    readonly_fields = ('event', 'note', 'round', 'actor', 'is_public', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'manuscript_id', 'short_title', 'section', 'status_badge', 'current_round',
        'handling_editor', 'apc_status', 'submitted_at', 'editor_link',
    )
    list_filter = ('status', 'section', 'apc_status', 'submitted_at')
    search_fields = (
        'manuscript_id', 'title', 'abstract', 'keywords',
        'submitter__email', 'authors__last_name', 'authors__email',
    )
    readonly_fields = ('manuscript_id', 'submitted_at', 'updated_at', 'decided_at', 'editor_link')
    inlines = [
        SubmissionAuthorInline, SubmissionFileInline, ScreeningReportInline,
        ReviewAssignmentInline, EditorialDecisionInline, ProofInline, SubmissionEventInline,
    ]
    date_hierarchy = 'submitted_at'

    def short_title(self, obj):
        return obj.title[:70] + ('…' if len(obj.title) > 70 else '')
    short_title.short_description = 'Title'

    def status_badge(self, obj):
        colours = {
            Submission.SUBMITTED: '#f59e0b',
            Submission.UNDER_REVIEW: '#2563eb',
            Submission.MINOR_REVISION: '#a855f7',
            Submission.MAJOR_REVISION: '#a855f7',
            Submission.RESUBMITTED: '#0891b2',
            Submission.ACCEPTED: '#16a34a',
            Submission.IN_PRODUCTION: '#16a34a',
            Submission.PUBLISHED: '#15803d',
        }
        colour = colours.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color:{}; font-weight:600; font-size:12px;">{}</span>',
            colour, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    def editor_link(self, obj):
        """Straight through to the editorial workflow, where the rules apply."""
        if not obj.pk:
            return '—'
        return format_html(
            '<a href="/jeltan/editor/submissions/{}/" target="_blank">Open in editor workflow</a>',
            obj.pk,
        )
    editor_link.short_description = 'Workflow'


@admin.register(EditorialDecision)
class EditorialDecisionAdmin(admin.ModelAdmin):
    """The decision record, for searching and for corrections.

    Read-only on purpose: recording a decision here would move nothing and send
    no letter, so the author would never learn of it. Decisions are made in the
    portal.
    """

    list_display = ('submission', 'decision', 'round', 'editor', 'decided_at', 'portal_link')
    list_filter = ('decision', 'decided_at', 'submission__section')
    search_fields = ('submission__manuscript_id', 'submission__title', 'letter_to_author')
    readonly_fields = ('submission', 'decision', 'round', 'editor', 'letter_to_author',
                       'share_reviews_with_author', 'decided_at')
    date_hierarchy = 'decided_at'

    def has_add_permission(self, request):
        return False

    def portal_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank">Open the manuscript</a>',
            reverse('journal:editor_submission', args=[obj.submission_id]),
        )
    portal_link.short_description = 'Workflow'


@admin.register(ReviewAssignment)
class ReviewAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'reviewer_name', 'submission', 'round', 'status', 'recommendation',
        'due_date', 'overdue_flag', 'invited_at',
    )
    list_filter = ('status', 'recommendation', 'due_date')
    search_fields = ('reviewer_name', 'reviewer_email', 'submission__manuscript_id')
    readonly_fields = ('token', 'invited_at', 'responded_at', 'completed_at')

    def overdue_flag(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color:#dc2626; font-weight:600;">Overdue</span>')
        return '—'
    overdue_flag.short_description = 'Overdue'


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('label', 'title', 'is_published', 'published_at', 'article_count')
    list_filter = ('is_published', 'year')
    search_fields = ('title', 'description')

    def article_count(self, obj):
        return obj.articles.count()
    article_count.short_description = 'Articles'


class ArticleAuthorInline(admin.TabularInline):
    model = ArticleAuthor
    extra = 1


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Published articles.

    Adding one by hand is supported on purpose: it is how the back catalogue —
    issues published before this system existed — gets into the archive.
    """

    list_display = ('title', 'issue', 'author_list', 'is_published', 'published_at', 'view_count', 'download_count')
    list_filter = ('is_published', 'issue', 'section')
    search_fields = ('title', 'abstract', 'keywords', 'doi', 'authors__last_name')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('view_count', 'download_count', 'created_at', 'updated_at')
    inlines = [ArticleAuthorInline]
    autocomplete_fields = ('submission',)
