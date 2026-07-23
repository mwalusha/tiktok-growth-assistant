from django.contrib import admin

from .models import TikTokAccount
from .models import ContentIdea
from .models import TikTokVideo
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
@admin.register(TikTokVideo)
class TikTokVideoAdmin(admin.ModelAdmin):
    list_display = (
        "video_id",
        "account",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
        "posted_at",
        "synced_at",
    )

    search_fields = (
        "video_id",
        "title",
        "description",
        "account__display_name",
    )

    list_filter = (
        "posted_at",
        "synced_at",
    )

    readonly_fields = (
        "synced_at",
    )