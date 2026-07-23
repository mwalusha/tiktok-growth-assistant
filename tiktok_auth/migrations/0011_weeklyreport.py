import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tiktok_auth", "0010_contentidea_calendar_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeeklyReport",
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
                ("week_start", models.DateField()),
                ("week_end", models.DateField()),
                (
                    "snapshot_deltas",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "creator_score",
                    models.PositiveSmallIntegerField(default=0),
                ),
                (
                    "creator_sub_scores",
                    models.JSONField(blank=True, default=dict),
                ),
                ("recommendation", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_reports",
                        to="tiktok_auth.tiktokaccount",
                    ),
                ),
                (
                    "best_video",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="best_in_weekly_reports",
                        to="tiktok_auth.tiktokvideo",
                    ),
                ),
                (
                    "worst_video",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="worst_in_weekly_reports",
                        to="tiktok_auth.tiktokvideo",
                    ),
                ),
            ],
            options={
                "ordering": ["-week_start"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("account", "week_start"),
                        name="unique_weekly_report_per_account",
                    ),
                ],
            },
        ),
    ]
