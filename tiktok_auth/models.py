from django.db import models


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

class TikTokVideo(models.Model):
    account = models.ForeignKey(
        TikTokAccount,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    video_id = models.CharField(
        max_length=255,
        unique=True,
    )

    title = models.TextField(
        blank=True,
    )

    description = models.TextField(
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
    def engagement_rate(self):
        if self.view_count == 0:
            return 0

        return round(
            self.total_engagement / self.view_count * 100,
            2,
        )
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
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

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

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    notes = models.TextField(
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

    def __str__(self):
        return self.title