from django.contrib import admin
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from .impersonation import can_impersonate
from .models import CustomUser, ImpersonationLog
from openpyxl import Workbook
from datetime import datetime




# Register your models here.
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'gender', 'is_active', 'date_joined',
                    'eltan_number']
    list_filter = ['is_active', 'is_staff', 'gender']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    actions = ['export_to_excel']

    def get_list_display(self, request):
        """Append the "Sign in as" column, built per request.

        The column has to know who is asking, and a plain ``list_display`` method
        is handed only the row. Building it here closes over this request's user
        instead of stashing it on the admin instance, which is a singleton shared
        by every concurrent request.
        """
        def impersonate_link(obj):
            # A link, not a button: the changelist is itself one big <form> and a
            # nested form is invalid HTML. It leads to a confirmation page that
            # carries the POST, which is the step we want anyway.
            if not can_impersonate(request.user, obj):
                return format_html('<span style="color:#9ca3af;">&mdash;</span>')
            url = reverse('impersonate_user', args=[obj.pk])
            return format_html(
                '<a href="{}" style="background:#7f1d1d; color:#fff; padding:3px 10px; '
                'border-radius:12px; font-size:11px; font-weight:600; text-decoration:none; '
                'white-space:nowrap;">Sign in as</a>', url,
            )
        impersonate_link.short_description = 'Impersonate'
        return list(super().get_list_display(request)) + [impersonate_link]

    def export_to_excel(self, request, queryset):
        wb = Workbook()
        ws = wb.active
        ws.title = "Users List"

        # Define headers
        headers = [
            'ID', 'Email', 'First Name', 'Last Name', 'Gender',
            'Is Active', 'Is Staff', 'Is Superuser', 'Date Joined',
            'Last Login'
        ]
        ws.append(headers)

        # Add data
        for user in queryset:
            row = [
                user.id,
                user.email,
                user.first_name,
                user.last_name,
                user.gender,
                'Yes' if user.is_active else 'No',
                'Yes' if user.is_staff else 'No',
                'Yes' if user.is_superuser else 'No',
                user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else 'Never'
            ]
            ws.append(row)

        # Style the worksheet
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[chr(64 + col)].width = 15  # Set column width

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=users_list_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb.save(response)
        return response

    export_to_excel.short_description = "Export selected users to Excel"
    
    
    
@admin.register(ImpersonationLog)
class ImpersonationLogAdmin(admin.ModelAdmin):
    """The record of who signed in as whom.

    Entirely read-only, including for superusers: an audit trail the people it
    audits can edit is not an audit trail. Rows are written by the impersonation
    views and closed when the session ends.
    """

    list_display = ('started_at', 'impersonator_email', 'target_email', 'duration_display',
                    'end_reason', 'ip_address')
    list_filter = ('end_reason', 'started_at')
    search_fields = ('impersonator_email', 'target_email', 'ip_address')
    date_hierarchy = 'started_at'
    ordering = ('-started_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def duration_display(self, obj):
        if obj.is_open:
            return format_html(
                '<span style="background:#fef2f2; color:#dc2626; border:1px solid #dc2626; '
                'padding:2px 9px; border-radius:12px; font-size:11px; font-weight:600;">IN PROGRESS</span>'
            )
        minutes, seconds = divmod(int(obj.duration.total_seconds()), 60)
        return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
    duration_display.short_description = 'Duration'


admin.site.register(CustomUser, CustomUserAdmin)

