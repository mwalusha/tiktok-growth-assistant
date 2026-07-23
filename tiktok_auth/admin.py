from django.contrib import admin

from .models import TikTokAccount
from .models import ContentIdea

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
@admin.register(ContentIdea)
class ContentIdeaAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "account",
        "category",
        "status",
        "planned_date",
        "created_at",
    )

    list_filter = (
        "category",
        "status",
    )

    search_fields = (
        "title",
        "hook",
        "caption",
        "hashtags",
    )
