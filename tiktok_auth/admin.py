from django.contrib import admin

from .models import TikTokAccount
from .models import ContentIdea
from .models import TikTokVideo
from .models import TikTokDailySnapshot
from .models import WeeklyReport
from .models import (
    ChatConversation,
    ChatMessage,
    PeerComparison,
)
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
        "is_generated",
        "planned_date",
        "created_at",
    )

    list_filter = (
        "category",
        "status",
        "is_generated",
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


@admin.register(TikTokDailySnapshot)
class TikTokDailySnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "date",
        "follower_count",
        "likes_count",
        "video_count",
        "average_video_views",
        "avg_engagement_rate",
    )
    list_filter = ("date",)
    search_fields = (
        "account__display_name",
        "account__open_id",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "week_start",
        "week_end",
        "creator_score",
        "updated_at",
    )
    list_filter = ("week_start",)
    search_fields = (
        "account__display_name",
        "account__open_id",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(PeerComparison)
class PeerComparisonAdmin(admin.ModelAdmin):
    list_display = (
        "requesting_account",
        "peer_account",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    readonly_fields = (
        "invite_token",
        "created_at",
        "accepted_at",
    )


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("role", "content", "created_at")
    can_delete = False


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ("account", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    inlines = (ChatMessageInline,)
