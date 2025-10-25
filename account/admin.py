from django.contrib import admin
from django.http import HttpResponse
from .models import CustomUser
from openpyxl import Workbook
from datetime import datetime




# Register your models here.
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'gender', 'is_active', 'date_joined', 'eltan_number']
    list_filter = ['is_active', 'is_staff', 'gender']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    actions = ['export_to_excel']

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
    
    
    
admin.site.register(CustomUser, CustomUserAdmin)

