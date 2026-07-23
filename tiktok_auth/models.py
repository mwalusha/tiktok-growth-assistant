from django.db import models


class TikTokAccount(models.Model):
    open_id = models.CharField(
        max_length=255,
        unique=True
    )

    display_name = models.CharField(
        max_length=255,
        blank=True
    )

    avatar_url = models.URLField(
        blank=True
    )

    access_token = models.TextField()

    refresh_token = models.TextField()

    access_token_expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    refresh_token_expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    scope = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.display_name or self.open_id
