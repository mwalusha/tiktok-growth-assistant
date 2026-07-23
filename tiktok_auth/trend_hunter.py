from collections import defaultdict
from datetime import timedelta
from statistics import mean

from django.utils import timezone


MIN_ACCOUNTS_PER_TREND = 2


def get_trend_hunter(account, limit=10) -> dict:
    """
    Aggregate anonymized hashtags from opted-in, similar creators.

    A hashtag is shown only when it appears across at least two accounts,
    preventing a single creator's private strategy from being exposed.
    """

    since = timezone.now() - timedelta(days=30)
    videos = (
        account.videos.model.objects.filter(
            account__allow_trend_aggregation=True,
            posted_at__gte=since,
        )
        .select_related("account")
        .order_by("account_id", "-view_count")
    )

    if account.niche:
        videos = videos.filter(
            account__niche__iexact=account.niche
        )

    by_account = defaultdict(list)

    for video in videos[:2000]:
        by_account[video.account_id].append(video)

    high_performers = []

    for account_videos in by_account.values():
        keep_count = max(1, (len(account_videos) + 3) // 4)
        high_performers.extend(account_videos[:keep_count])

    hashtag_data = defaultdict(
        lambda: {
            "accounts": set(),
            "engagement_rates": [],
            "video_count": 0,
            "display": "",
        }
    )

    for video in high_performers:
        engagement_rate = (
            (
                video.like_count
                + video.comment_count
                + video.share_count
            )
            / video.view_count
            * 100
            if video.view_count
            else 0
        )

        for hashtag in set(video.hashtags or []):
            normalized = str(hashtag).lstrip("#").casefold()

            if not normalized:
                continue

            data = hashtag_data[normalized]
            data["accounts"].add(video.account_id)
            data["engagement_rates"].append(engagement_rate)
            data["video_count"] += 1
            data["display"] = str(hashtag).lstrip("#")

    trends = []

    for normalized, data in hashtag_data.items():
        account_count = len(data["accounts"])

        if account_count < MIN_ACCOUNTS_PER_TREND:
            continue

        avg_engagement = mean(data["engagement_rates"])
        trends.append(
            {
                "hashtag": data["display"],
                "normalized": normalized,
                "account_count": account_count,
                "video_count": data["video_count"],
                "avg_engagement_rate": round(
                    avg_engagement,
                    2,
                ),
                "trend_score": round(
                    account_count * 40
                    + data["video_count"] * 10
                    + min(avg_engagement, 20),
                    2,
                ),
            }
        )

    trends.sort(
        key=lambda item: (
            item["trend_score"],
            item["avg_engagement_rate"],
        ),
        reverse=True,
    )
    return {
        "trends": trends[:limit],
        "participating_accounts": len(by_account),
        "lookback_days": 30,
        "sounds_available": False,
        "is_opted_in": account.allow_trend_aggregation,
        "privacy_threshold": MIN_ACCOUNTS_PER_TREND,
    }


def get_trending_hashtag_names(account) -> list[str] | None:
    trends = get_trend_hunter(account)["trends"]
    return (
        [trend["hashtag"] for trend in trends]
        if trends
        else None
    )
