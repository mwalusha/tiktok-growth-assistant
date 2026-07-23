import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tiktok_auth", "0011_weeklyreport"),
    ]

    operations = [
        migrations.AddField(
            model_name="tiktokaccount",
            name="allow_peer_comparison",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tiktokaccount",
            name="allow_trend_aggregation",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="ChatConversation",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_conversation",
                        to="tiktok_auth.tiktokaccount",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PeerComparison",
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
                (
                    "invite_token",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "accepted_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "peer_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comparison_requests_received",
                        to="tiktok_auth.tiktokaccount",
                    ),
                ),
                (
                    "requesting_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comparison_requests_sent",
                        to="tiktok_auth.tiktokaccount",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ChatMessage",
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
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("user", "User"),
                            ("assistant", "Assistant"),
                        ],
                        max_length=20,
                    ),
                ),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="tiktok_auth.chatconversation",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
    ]
