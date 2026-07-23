from datetime import timedelta
from statistics import mean

from django.utils import timezone


def _account_metrics(account) -> dict:
    since = timezone.now() - timedelta(days=28)
    videos = list(
        account.videos.filter(posted_at__gte=since)
    )
    engagement_rates = [
        (
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
        for video in videos
    ]
    return {
        "followers": account.follower_count,
        "posts_last_28_days": len(videos),
        "posts_per_week": round(len(videos) / 4, 1),
        "average_engagement_rate": round(
            mean(engagement_rates)
            if engagement_rates
            else 0,
            2,
        ),
        "average_views": round(
            mean(video.view_count for video in videos)
            if videos
            else 0,
        ),
    }


def build_peer_comparison(comparison, viewing_account):
    if viewing_account == comparison.requesting_account:
        own = comparison.requesting_account
        peer = comparison.peer_account
    else:
        own = comparison.peer_account
        peer = comparison.requesting_account

    own_metrics = _account_metrics(own)
    peer_metrics = _account_metrics(peer)
    return {
        "comparison": comparison,
        "peer": peer,
        "own": own_metrics,
        "peer_metrics": peer_metrics,
        "differences": {
            key: round(
                own_metrics[key] - peer_metrics[key],
                2,
            )
            for key in own_metrics
        },
    }
