from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tiktok_auth", "0006_alter_tiktokvideo_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tiktokvideo",
            name="hashtags",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
