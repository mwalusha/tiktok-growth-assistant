from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("tiktok_auth", "0014_personal_analytics_refactor"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentidea",
            name="confidence",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="concept",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="source_video",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generated_content_ideas",
                to="tiktok_auth.tiktokvideo",
            ),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="topic",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
