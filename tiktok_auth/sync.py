import logging
from datetime import timedelta
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    TikTokAccount,
    TikTokDailySnapshot,
    TikTokVideo,
)
from .services import (
    TikTokAPIError,
    get_all_tiktok_videos,
    get_tiktok_profile,
    refresh_access_token,
)
from .utils import extract_hashtags


logger = logging.getLogger(__name__)
TOKEN_REFRESH_BUFFER = timedelta(minutes=5)
def safe_non_negative_int(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def ensure_valid_access_token(account: TikTokAccount) -> str:
    """
    Refresh an access token before an API call when it is near expiry.

    A short buffer keeps a token from expiring during a paginated sync.
    """

    expires_at = account.access_token_expires_at

    if (
        account.access_token
        and expires_at
        and expires_at > timezone.now() + TOKEN_REFRESH_BUFFER
    ):
        return account.access_token

    if not account.refresh_token:
        raise TikTokAPIError(
            "The TikTok access token has expired and no refresh token "
            "is available. Reconnect the account."
        )

    if (
        account.refresh_token_expires_at
        and account.refresh_token_expires_at <= timezone.now()
    ):
        raise TikTokAPIError(
            "The TikTok refresh token has expired. Reconnect the account."
        )

    token_data = refresh_access_token(account.refresh_token)
    access_token = token_data.get("access_token")

    if not access_token:
        raise TikTokAPIError(
            "TikTok did not return an access token while refreshing."
        )

    try:
        expires_in = int(token_data.get("expires_in") or 0)
        refresh_expires_in = int(
            token_data.get("refresh_expires_in") or 0
        )
    except (TypeError, ValueError) as exc:
        raise TikTokAPIError(
            "TikTok returned invalid token expiry information."
        ) from exc

    account.access_token = access_token
    account.access_token_expires_at = (
        timezone.now() + timedelta(seconds=expires_in)
        if expires_in
        else None
    )

    if token_data.get("refresh_token"):
        account.refresh_token = token_data["refresh_token"]

    if refresh_expires_in:
        account.refresh_token_expires_at = (
            timezone.now()
            + timedelta(seconds=refresh_expires_in)
        )

    if token_data.get("scope"):
        account.scope = token_data["scope"]

    account.save(
        update_fields=[
            "access_token",
            "access_token_expires_at",
            "refresh_token",
            "refresh_token_expires_at",
            "scope",
            "updated_at",
        ]
    )

    return account.access_token


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


def calculate_snapshot_metrics(
    videos: list[TikTokVideo],
) -> dict:
    """Aggregate the public videos active in the current sync."""

    total_views = sum(video.view_count for video in videos)
    total_video_likes = sum(video.like_count for video in videos)
    total_comments = sum(video.comment_count for video in videos)
    total_shares = sum(video.share_count for video in videos)

    rates = [
        (
            Decimal(
                video.like_count
                + video.comment_count
                + video.share_count
            )
            / Decimal(video.view_count)
            * Decimal("100")
            if video.view_count
            else Decimal("0")
        )
        for video in videos
    ]
    avg_engagement_rate = (
        sum(rates, Decimal("0")) / Decimal(len(rates))
        if rates
        else Decimal("0")
    )

    return {
        "total_views": total_views,
        "average_video_views": (
            total_views / len(videos) if videos else 0
        ),
        "total_video_likes": total_video_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "avg_engagement_rate": avg_engagement_rate.quantize(
            Decimal("0.0001")
        ),
    }


def sync_tiktok_performance(
    account: TikTokAccount,
) -> dict:
    """
    Update profile statistics and synchronize public videos.
    """

    # The sync owns token validation so cron and web-triggered runs cannot
    # accidentally call TikTok with a stale 24-hour access token.
    access_token = ensure_valid_access_token(account)
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
    account.follower_count = safe_non_negative_int(
        profile.get("follower_count")
    )
    account.following_count = safe_non_negative_int(
        profile.get("following_count")
    )
    account.likes_count = safe_non_negative_int(
        profile.get("likes_count")
    )
    account.video_count = safe_non_negative_int(
        profile.get("video_count")
    )

    videos = get_all_tiktok_videos(access_token)

    created_count = 0
    updated_count = 0
    active_videos = []

    with transaction.atomic():
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

        for video_data in videos:
            video_id = str(video_data.get("id", "")).strip()

            if not video_id:
                logger.warning(
                    "TikTok returned a video without an ID."
                )
                continue

            description = video_data.get(
                "video_description",
                "",
            ) or ""
            video, created = TikTokVideo.objects.update_or_create(
                account=account,
                video_id=video_id,
                defaults={
                    "title": video_data.get("title", "") or "",
                    "description": description,
                    "hashtags": extract_hashtags(description),
                    "cover_image_url": video_data.get(
                        "cover_image_url",
                        "",
                    ) or "",
                    "share_url": video_data.get(
                        "share_url",
                        "",
                    ) or "",
                    "embed_link": video_data.get(
                        "embed_link",
                        "",
                    ) or "",
                    "duration": safe_non_negative_int(
                        video_data.get("duration")
                    ),
                    "view_count": safe_non_negative_int(
                        video_data.get("view_count")
                    ),
                    "like_count": safe_non_negative_int(
                        video_data.get("like_count")
                    ),
                    "comment_count": safe_non_negative_int(
                        video_data.get("comment_count")
                    ),
                    "share_count": safe_non_negative_int(
                        video_data.get("share_count")
                    ),
                    "posted_at": unix_timestamp_to_datetime(
                        video_data.get("create_time")
                    ),
                },
            )
            active_videos.append(video)

            if created:
                created_count += 1
            else:
                updated_count += 1

        snapshot_metrics = calculate_snapshot_metrics(
            active_videos
        )
        snapshot, snapshot_created = (
            TikTokDailySnapshot.objects.update_or_create(
                account=account,
                date=timezone.localdate(),
                defaults={
                    "follower_count": account.follower_count,
                    "following_count": account.following_count,
                    "likes_count": account.likes_count,
                    "video_count": account.video_count,
                    **snapshot_metrics,
                },
            )
        )

    return {
        "profile_updated": True,
        "profile": profile,
        "videos_received": len(videos),
        "videos_saved": created_count + updated_count,
        "videos_created": created_count,
        "videos_updated": updated_count,
        "snapshot": snapshot,
        "snapshot_created": snapshot_created,
        "snapshot_updated": not snapshot_created,
        "synced_at": timezone.now(),
    }
