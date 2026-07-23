from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tiktok_auth", "0008_tiktokdailysnapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="tiktokaccount",
            name="niche",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
