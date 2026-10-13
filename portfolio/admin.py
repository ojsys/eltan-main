from django.contrib import admin

from .models import Achievement, PortfolioProfile, PortfolioSettings, PremiumGrant


@admin.register(PortfolioSettings)
class PortfolioSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'premium_enabled', 'free_upload_limit')

    def has_add_permission(self, request):
        return not PortfolioSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PremiumGrant)
class PremiumGrantAdmin(admin.ModelAdmin):
    list_display = ('user', 'starts_on', 'ends_on', 'note')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'note')
    raw_id_fields = ('user',)


@admin.register(PortfolioProfile)
class PortfolioProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'headline', 'cpd_goal_hours', 'share_enabled', 'updated_at')
    list_filter = ('share_enabled',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'headline')
    raw_id_fields = ('user',)
    readonly_fields = ('share_token',)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """Members' self-reported records. Listed for support and reporting, not for editing."""

    list_display = ('title', 'user', 'category', 'completed_on', 'cpd_hours', 'has_evidence')
    list_filter = ('category',)
    search_fields = ('title', 'provider', 'user__email', 'user__last_name')
    raw_id_fields = ('user',)
    date_hierarchy = 'completed_on'

    @admin.display(boolean=True, description='Evidence')
    def has_evidence(self, obj):
        return bool(obj.evidence)
