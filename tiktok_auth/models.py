import uuid

from django.db import models


class TikTokAccount(models.Model):
    open_id = models.CharField(
        max_length=255,
        unique=True,
    )

    display_name = models.CharField(
        max_length=255,
        blank=True,
    )

    username = models.CharField(
        max_length=255,
        blank=True,
    )

    avatar_url = models.URLField(
        max_length=1000,
        blank=True,
    )

    profile_deep_link = models.URLField(
        max_length=1000,
        blank=True,
    )

    bio_description = models.TextField(
        blank=True,
    )

    is_verified = models.BooleanField(
        default=False,
    )

    follower_count = models.PositiveBigIntegerField(
        default=0,
    )

    following_count = models.PositiveBigIntegerField(
        default=0,
    )

    likes_count = models.PositiveBigIntegerField(
        default=0,
    )

    video_count = models.PositiveBigIntegerField(
        default=0,
    )

    niche = models.CharField(
        max_length=160,
        blank=True,
    )

    allow_trend_aggregation = models.BooleanField(
        default=False,
    )

    allow_peer_comparison = models.BooleanField(
        default=False,
    )

    access_token = models.TextField()

    refresh_token = models.TextField(
        blank=True,
    )

    scope = models.TextField(
        blank=True,
    )

    access_token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    refresh_token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.display_name or self.open_id

    @property
    def snapshots(self):
        return self.daily_snapshots

class TikTokVideo(models.Model):
    account = models.ForeignKey(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    video_id = models.CharField(max_length=100)

    title = models.TextField(
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    hashtags = models.JSONField(
        default=list,
        blank=True,
    )

    cover_image_url = models.URLField(
        max_length=1500,
        blank=True,
    )

    share_url = models.URLField(
        max_length=1500,
        blank=True,
    )

    embed_link = models.URLField(
        max_length=1500,
        blank=True,
    )

    duration = models.PositiveIntegerField(
        default=0,
    )

    view_count = models.PositiveBigIntegerField(
        default=0,
    )

    like_count = models.PositiveBigIntegerField(
        default=0,
    )

    comment_count = models.PositiveBigIntegerField(
        default=0,
    )

    share_count = models.PositiveBigIntegerField(
        default=0,
    )

    posted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    synced_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-posted_at", "-view_count"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "video_id"],
                name="unique_tiktok_video_per_account",
            ),
        ]
        indexes = [
            models.Index(
                fields=["account", "-posted_at"],
                name="video_account_posted_idx",
            ),
            models.Index(
                fields=["account", "-view_count"],
                name="video_account_views_idx",
            ),
        ]

    def __str__(self):
        return self.title or self.video_id

    @property
    def total_engagement(self):
        return (
            self.like_count
            + self.comment_count
            + self.share_count
        )

    @property
    def total_engagements(self):
        return self.total_engagement

    @property
    def engagement_rate(self):
        if self.view_count == 0:
            return 0

        return round(
            self.total_engagement / self.view_count * 100,
            2,
        )


class TikTokDailySnapshot(models.Model):
    account = models.ForeignKey(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="daily_snapshots",
    )

    date = models.DateField()

    follower_count = models.PositiveBigIntegerField(
        default=0,
    )

    following_count = models.PositiveBigIntegerField(
        default=0,
    )

    likes_count = models.PositiveBigIntegerField(
        default=0,
    )

    video_count = models.PositiveBigIntegerField(
        default=0,
    )

    total_views = models.PositiveBigIntegerField(
        default=0,
    )

    average_video_views = models.FloatField(default=0)

    total_video_likes = models.PositiveBigIntegerField(
        default=0,
    )

    total_comments = models.PositiveBigIntegerField(
        default=0,
    )

    total_shares = models.PositiveBigIntegerField(
        default=0,
    )

    avg_engagement_rate = models.DecimalField(
        max_digits=9,
        decimal_places=4,
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "date"],
                name="unique_daily_snapshot_per_account",
            ),
        ]

    def __str__(self):
        return f"{self.account} — {self.date}"

    @property
    def snapshot_date(self):
        return self.date

    @property
    def total_video_views(self):
        return self.total_views

    @property
    def average_engagement_rate(self):
        return self.avg_engagement_rate


# Canonical name for new code; the historical name remains migration-safe.
TikTokAccountSnapshot = TikTokDailySnapshot


class WeeklyReport(models.Model):
    account = models.ForeignKey(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="weekly_reports",
    )
    week_start = models.DateField()
    week_end = models.DateField()
    snapshot_deltas = models.JSONField(
        default=dict,
        blank=True,
    )
    creator_score = models.PositiveSmallIntegerField(
        default=0,
    )
    creator_sub_scores = models.JSONField(
        default=dict,
        blank=True,
    )
    recommendation = models.TextField(blank=True)
    best_video = models.ForeignKey(
        TikTokVideo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="best_in_weekly_reports",
    )
    worst_video = models.ForeignKey(
        TikTokVideo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="worst_in_weekly_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "week_start"],
                name="unique_weekly_report_per_account",
            ),
        ]

    def __str__(self):
        return f"{self.account} — week of {self.week_start}"


class PeerComparison(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"

    invite_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    requesting_account = models.ForeignKey(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="comparison_requests_sent",
    )
    peer_account = models.ForeignKey(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="comparison_requests_received",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.requesting_account} comparison "
            f"({self.get_status_display()})"
        )


class ChatConversation(models.Model):
    account = models.OneToOneField(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="chat_conversation",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Assistant chat — {self.account}"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"


class ContentIdea(models.Model):
    class Category(models.TextChoices):
        EDUCATIONAL = "educational", "Educational"
        TUTORIAL = "tutorial", "Tutorial"
        RELATABLE = "relatable", "Relatable"
        PROMOTIONAL = "promotional", "Promotional"
        STORY = "story", "Story"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready to Post"
        FILMED = "filmed", "Filmed"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class ContentType(models.TextChoices):
        EDUCATIONAL = "educational", "Educational"
        TUTORIAL = "tutorial", "Tutorial"
        TRANSFORMATION = "transformation", "Transformation"
        STORY = "story", "Story"
        COMMUNITY = "community", "Community"
        PROMOTIONAL = "promotional", "Promotional"

    account = models.ForeignKey(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="content_ideas",
    )

    title = models.CharField(
        max_length=200,
    )

    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.EDUCATIONAL,
    )

    content_type = models.CharField(
        max_length=30,
        choices=ContentType.choices,
        blank=True,
    )

    hook = models.CharField(
        max_length=300,
        blank=True,
    )

    script = models.TextField(
        blank=True,
    )

    caption = models.TextField(
        blank=True,
    )

    hashtags = models.CharField(
        max_length=500,
        blank=True,
    )

    planned_date = models.DateTimeField(
        null=True,
        blank=True,
    )

    calendar_date = models.DateField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    notes = models.TextField(
        blank=True,
    )

    reason = models.TextField(
        blank=True,
    )

    suggested_length = models.CharField(
        max_length=100,
        blank=True,
    )

    suggested_posting_time = models.CharField(
        max_length=160,
        blank=True,
    )

    is_generated = models.BooleanField(default=False)

    generation_reason = models.TextField(blank=True)

    suggested_duration = models.CharField(
        max_length=100,
        blank=True,
    )

    suggested_posting_day = models.CharField(
        max_length=20,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "calendar_date"],
                condition=models.Q(
                    calendar_date__isnull=False
                ),
                name="unique_ai_calendar_day_per_account",
            ),
        ]

    def __str__(self):
        return self.title
