import logging
from datetime import datetime, timezone as datetime_timezone

from django.db import transaction

from .models import TikTokAccount, TikTokVideo
from .services import (
    get_all_tiktok_videos,
    get_tiktok_profile,
)


logger = logging.getLogger(__name__)


def unix_timestamp_to_datetime(value):
    if value in (None, ""):
        return None

    try:
        return datetime.fromtimestamp(
            int(value),
            tz=datetime_timezone.utc,
        )
    except (TypeError, ValueError, OverflowError):
        return None


@transaction.atomic
def sync_tiktok_performance(
    account: TikTokAccount,
    access_token: str,
) -> dict:
    """
    Update profile statistics and synchronize public videos.
    """

    profile = get_tiktok_profile(access_token)

    account.display_name = profile.get(
        "display_name",
        account.display_name,
    )
    account.username = profile.get(
        "username",
        account.username,
    )
    account.avatar_url = profile.get(
        "avatar_url",
        account.avatar_url,
    )
    account.profile_deep_link = profile.get(
        "profile_deep_link",
        account.profile_deep_link,
    )
    account.bio_description = profile.get(
        "bio_description",
        account.bio_description,
    )
    account.is_verified = profile.get(
        "is_verified",
        account.is_verified,
    )
    account.follower_count = profile.get(
        "follower_count",
        0,
    )
    account.following_count = profile.get(
        "following_count",
        0,
    )
    account.likes_count = profile.get(
        "likes_count",
        0,
    )
    account.video_count = profile.get(
        "video_count",
        0,
    )

    account.save(
        update_fields=[
            "display_name",
            "username",
            "avatar_url",
            "profile_deep_link",
            "bio_description",
            "is_verified",
            "follower_count",
            "following_count",
            "likes_count",
            "video_count",
            "updated_at",
        ]
    )

    videos = get_all_tiktok_videos(access_token)

    synced_ids = []

    for video_data in videos:
        video_id = str(video_data.get("id", "")).strip()

        if not video_id:
            logger.warning(
                "TikTok returned a video without an ID."
            )
            continue

        TikTokVideo.objects.update_or_create(
            account=account,
            video_id=video_id,
            defaults={
                "title": video_data.get("title", ""),
                "description": video_data.get(
                    "video_description",
                    "",
                ),
                "cover_image_url": video_data.get(
                    "cover_image_url",
                    "",
                ),
                "share_url": video_data.get(
                    "share_url",
                    "",
                ),
                "embed_link": video_data.get(
                    "embed_link",
                    "",
                ),
                "duration": video_data.get(
                    "duration",
                    0,
                ) or 0,
                "view_count": video_data.get(
                    "view_count",
                    0,
                ) or 0,
                "like_count": video_data.get(
                    "like_count",
                    0,
                ) or 0,
                "comment_count": video_data.get(
                    "comment_count",
                    0,
                ) or 0,
                "share_count": video_data.get(
                    "share_count",
                    0,
                ) or 0,
                "posted_at": unix_timestamp_to_datetime(
                    video_data.get("create_time")
                ),
            },
        )

        synced_ids.append(video_id)

    return {
        "profile": profile,
        "videos_received": len(videos),
        "videos_saved": len(synced_ids),
    }
