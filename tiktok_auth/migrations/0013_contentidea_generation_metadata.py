from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tiktok_auth", "0012_peer_trend_chat"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentidea",
            name="reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="suggested_length",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="contentidea",
            name="suggested_posting_time",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
