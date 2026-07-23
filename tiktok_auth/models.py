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

    avatar_url = models.URLField(
        max_length=1000,
        blank=True,
    )

    access_token = models.TextField()

    refresh_token = models.TextField(
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

    scope = models.TextField(
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