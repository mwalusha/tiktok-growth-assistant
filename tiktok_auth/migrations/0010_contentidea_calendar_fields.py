from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tiktok_auth", "0009_tiktokaccount_niche"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentidea",
            name="calendar_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="content_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("educational", "Educational"),
                    ("tutorial", "Tutorial"),
                    ("transformation", "Transformation"),
                    ("story", "Story"),
                    ("community", "Community"),
                    ("promotional", "Promotional"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddConstraint(
            model_name="contentidea",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("calendar_date__isnull", False)
                ),
                fields=("account", "calendar_date"),
                name="unique_ai_calendar_day_per_account",
            ),
        ),
    ]
