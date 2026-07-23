from collections import defaultdict
from datetime import timedelta
from statistics import mean

from django.db.models import Avg, Count, Max, Sum
from django.utils import timezone

from .models import TikTokAccount, TikTokDailySnapshot, TikTokVideo
from .utils import classify_topic


def safe_percentage(numerator, denominator) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator) * 100, 2)


def classify_video_length(duration: int) -> str:
    if duration <= 0:
        return "Unknown"
    if duration <= 10:
        return "0–10 seconds"
    if duration <= 20:
        return "11–20 seconds"
    if duration <= 30:
        return "21–30 seconds"
    if duration <= 60:
        return "31–60 seconds"
    return "61+ seconds"


def build_video_metrics(video: TikTokVideo) -> dict:
    return {
        "video": video,
        "engagement_count": video.total_engagement,
        "engagement_rate": safe_percentage(
            video.total_engagement, video.view_count
        ),
        "like_rate": safe_percentage(video.like_count, video.view_count),
        "comment_rate": safe_percentage(
            video.comment_count, video.view_count
        ),
        "share_rate": safe_percentage(video.share_count, video.view_count),
    }


def _performance_rows(groups, label_key):
    rows = []
    for label, videos in groups.items():
        if not videos:
            continue
        rows.append(
            {
                label_key: label,
                "label": label,
                "video_count": len(videos),
                "average_views": round(
                    mean(video.view_count for video in videos), 2
                ),
                "average_engagement_rate": round(
                    mean(
                        safe_percentage(
                            video.total_engagement, video.view_count
                        )
                        for video in videos
                    ),
                    2,
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["average_views"],
            row["average_engagement_rate"],
            row["video_count"],
        ),
        reverse=True,
    )


def calculate_length_performance(videos) -> list[dict]:
    groups = defaultdict(list)
    for video in videos:
        label = classify_video_length(video.duration)
        if label != "Unknown":
            groups[label].append(video)
    return _performance_rows(groups, "length")


def calculate_day_performance(videos) -> list[dict]:
    groups = defaultdict(list)
    for video in videos:
        if video.posted_at:
            local_time = timezone.localtime(video.posted_at)
            groups[local_time.strftime("%A")].append(video)
    return _performance_rows(groups, "day")


def _time_window(hour: int) -> str:
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 22:
        return "Evening"
    return "Late night"


def calculate_time_performance(videos) -> list[dict]:
    groups = defaultdict(list)
    for video in videos:
        if video.posted_at:
            local_time = timezone.localtime(video.posted_at)
            groups[_time_window(local_time.hour)].append(video)
    return _performance_rows(groups, "time")


def calculate_topic_performance(videos) -> list[dict]:
    groups = defaultdict(list)
    for video in videos:
        text = " ".join(
            [video.title or "", video.description or ""]
            + [str(tag) for tag in (video.hashtags or [])]
        )
        groups[classify_topic(text)].append(video)
    return _performance_rows(groups, "topic")


def _snapshot_percentage(current, previous, field):
    if not current or not previous:
        return 0.0
    old = getattr(previous, field)
    return safe_percentage(getattr(current, field) - old, old)


def get_daily_growth(account: TikTokAccount, target_date=None) -> dict:
    """Compare the latest two available snapshots, even if a day was missed."""

    snapshots = list(
        TikTokDailySnapshot.objects.filter(account=account)
        .order_by("-date")[:2]
    )
    current = snapshots[0] if snapshots else None
    previous = snapshots[1] if len(snapshots) > 1 else None
    fields = (
        "follower_count",
        "following_count",
        "likes_count",
        "video_count",
        "total_views",
        "total_video_likes",
        "total_comments",
        "total_shares",
        "avg_engagement_rate",
    )
    deltas = {}
    if current and previous:
        deltas = {
            field: getattr(current, field) - getattr(previous, field)
            for field in fields
        }
    return {
        "today": current,
        "yesterday": previous,
        "latest": current,
        "previous": previous,
        "deltas": deltas,
        "has_comparison": bool(current and previous),
    }


def generate_recommendations(
    account, videos, average_views, engagement_rate,
    length_performance, day_performance, top_video_metrics,
):
    if not videos:
        return [{
            "title": "Sync your TikTok videos",
            "message": "Run a sync to unlock recommendations from your posts.",
            "priority": "high",
        }]
    recommendations = []
    if length_performance:
        best = length_performance[0]
        recommendations.append({
            "title": f"Create more {best['label']} videos",
            "message": (
                f"This length averages {best['average_views']:,.0f} views "
                "across your synced posts."
            ),
            "priority": "high",
        })
    if day_performance:
        best = day_performance[0]
        recommendations.append({
            "title": f"Test more posts on {best['day']}",
            "message": (
                f"Your {best['day']} posts average "
                f"{best['average_engagement_rate']:.2f}% engagement."
            ),
            "priority": "medium",
        })
    if top_video_metrics:
        subject = (
            top_video_metrics[0]["video"].title
            or top_video_metrics[0]["video"].description
            or "your leading post"
        )
        recommendations.append({
            "title": "Make a follow-up to your strongest post",
            "message": f'Build a sequel around “{subject[:90]}”.',
            "priority": "high",
        })
    return recommendations


def get_account_analytics(account: TikTokAccount) -> dict:
    queryset = account.videos.all()
    aggregate = queryset.aggregate(
        total_views=Sum("view_count"),
        total_likes=Sum("like_count"),
        total_comments=Sum("comment_count"),
        total_shares=Sum("share_count"),
        average_views=Avg("view_count"),
        average_likes=Avg("like_count"),
        average_comments=Avg("comment_count"),
        average_shares=Avg("share_count"),
        highest_views=Max("view_count"),
        videos_analyzed=Count("id"),
    )
    videos = list(queryset.order_by("-view_count", "-like_count"))
    total_views = aggregate["total_views"] or 0
    total_likes = aggregate["total_likes"] or 0
    total_comments = aggregate["total_comments"] or 0
    total_shares = aggregate["total_shares"] or 0
    total_engagement = total_likes + total_comments + total_shares
    average_views = round(aggregate["average_views"] or 0, 2)
    average_engagement_rate = (
        round(
            mean(
                safe_percentage(video.total_engagement, video.view_count)
                for video in videos
            ),
            2,
        )
        if videos
        else 0.0
    )

    top_videos = [build_video_metrics(video) for video in videos[:5]]
    lowest_videos = [
        build_video_metrics(video)
        for video in sorted(
            videos,
            key=lambda video: (video.view_count, video.total_engagement),
        )[:5]
    ]
    recent_videos = [
        build_video_metrics(video)
        for video in sorted(
            videos,
            key=lambda video: (
                video.posted_at is not None,
                video.posted_at or timezone.now() - timedelta(days=36500),
            ),
            reverse=True,
        )[:6]
    ]
    length_performance = calculate_length_performance(videos)
    day_performance = calculate_day_performance(videos)
    time_performance = calculate_time_performance(videos)
    topic_performance = calculate_topic_performance(videos)
    growth = get_daily_growth(account)
    latest = growth["latest"]
    previous = growth["previous"]
    follower_change = (
        latest.follower_count - previous.follower_count
        if latest and previous else 0
    )
    engagement_change = (
        float(latest.avg_engagement_rate - previous.avg_engagement_rate)
        if latest and previous else 0.0
    )
    recommendations = generate_recommendations(
        account, videos, average_views, average_engagement_rate,
        length_performance, day_performance, top_videos,
    )
    best_day = day_performance[0] if day_performance else None
    best_time = time_performance[0] if time_performance else None

    return {
        "videos_analyzed": aggregate["videos_analyzed"] or 0,
        "total_views": total_views,
        "total_video_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_engagement": total_engagement,
        "average_views": average_views,
        "average_likes": round(aggregate["average_likes"] or 0, 2),
        "average_comments": round(
            aggregate["average_comments"] or 0, 2
        ),
        "average_shares": round(aggregate["average_shares"] or 0, 2),
        "highest_views": aggregate["highest_views"] or 0,
        "overall_engagement_rate": safe_percentage(
            total_engagement, total_views
        ),
        "average_engagement_rate": average_engagement_rate,
        "views_per_follower": safe_percentage(
            average_views, account.follower_count
        ),
        "top_videos": top_videos,
        "lowest_videos": lowest_videos,
        "recent_videos": recent_videos,
        "length_performance": length_performance,
        "day_performance": day_performance,
        "time_performance": time_performance,
        "topic_performance": topic_performance,
        "best_topic": topic_performance[0] if topic_performance else None,
        "best_length": (
            length_performance[0] if length_performance else None
        ),
        "best_video_length": (
            length_performance[0] if length_performance else None
        ),
        "best_day": best_day,
        "best_posting_day": best_day,
        "best_posting_time": best_time,
        "latest_snapshot": latest,
        "previous_snapshot": previous,
        "follower_change": follower_change,
        "follower_change_percentage": _snapshot_percentage(
            latest, previous, "follower_count"
        ),
        "likes_change": (
            latest.likes_count - previous.likes_count
            if latest and previous else 0
        ),
        "likes_change_percentage": _snapshot_percentage(
            latest, previous, "likes_count"
        ),
        "views_change": (
            latest.total_views - previous.total_views
            if latest and previous else 0
        ),
        "views_change_percentage": _snapshot_percentage(
            latest, previous, "total_views"
        ),
        "engagement_change": engagement_change,
        "engagement_change_percentage": _snapshot_percentage(
            latest, previous, "avg_engagement_rate"
        ),
        "recommendations": recommendations,
        "has_enough_data": len(videos) >= 3,
        "summary": {
            "top_topic": (
                topic_performance[0]["topic"] if topic_performance else None
            ),
            "best_length": (
                length_performance[0]["label"]
                if length_performance else None
            ),
            "best_day": best_day["day"] if best_day else None,
            "best_time": best_time["time"] if best_time else None,
        },
    }
