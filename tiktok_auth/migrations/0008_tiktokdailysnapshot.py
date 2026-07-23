import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tiktok_auth", "0007_tiktokvideo_hashtags"),
    ]

    operations = [
        migrations.CreateModel(
            name="TikTokDailySnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField()),
                (
                    "follower_count",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "following_count",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "likes_count",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "video_count",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "total_views",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "total_video_likes",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "total_comments",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "total_shares",
                    models.PositiveBigIntegerField(default=0),
                ),
                (
                    "avg_engagement_rate",
                    models.DecimalField(
                        decimal_places=4,
                        default=0,
                        max_digits=9,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_snapshots",
                        to="tiktok_auth.tiktokaccount",
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("account", "date"),
                        name="unique_daily_snapshot_per_account",
                    ),
                ],
            },
        ),
    ]
