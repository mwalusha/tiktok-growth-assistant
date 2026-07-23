from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tiktok_auth", "0013_contentidea_generation_metadata"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tiktokvideo",
            name="video_id",
            field=models.CharField(max_length=100),
        ),
        migrations.AddConstraint(
            model_name="tiktokvideo",
            constraint=models.UniqueConstraint(
                fields=("account", "video_id"),
                name="unique_tiktok_video_per_account",
            ),
        ),
        migrations.AddIndex(
            model_name="tiktokvideo",
            index=models.Index(
                fields=["account", "-posted_at"],
                name="video_account_posted_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="tiktokvideo",
            index=models.Index(
                fields=["account", "-view_count"],
                name="video_account_views_idx",
            ),
        ),
        migrations.AddField(
            model_name="tiktokdailysnapshot",
            name="average_video_views",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="generation_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="is_generated",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="suggested_duration",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="suggested_posting_day",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="contentidea",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("ready", "Ready to Post"),
                    ("filmed", "Filmed"),
                    ("published", "Published"),
                    ("archived", "Archived"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
    ]
