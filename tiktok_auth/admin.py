from django.contrib import admin

from .models import TikTokAccount


@admin.register(TikTokAccount)
class TikTokAccountAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "open_id",
        "scope",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "display_name",
        "open_id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    # Do not expose sensitive tokens in the admin interface.
    exclude = (
        "access_token",
        "refresh_token",
    )
