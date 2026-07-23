from collections import defaultdict
from datetime import timedelta
from statistics import mean

from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    Max,
    Sum,
)
from django.utils import timezone

from .models import (
    TikTokAccount,
    TikTokDailySnapshot,
    TikTokVideo,
)


def get_daily_growth(
    account: TikTokAccount,
    target_date=None,
) -> dict:
    """Compare an account snapshot with the preceding calendar day."""

    target_date = target_date or timezone.localdate()
    snapshots = {
        snapshot.date: snapshot
        for snapshot in TikTokDailySnapshot.objects.filter(
            account=account,
            date__in=[
                target_date,
                target_date - timedelta(days=1),
            ],
        )
    }
    today = snapshots.get(target_date)
    yesterday = snapshots.get(
        target_date - timedelta(days=1)
    )
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

    if today and yesterday:
        deltas = {
            field: getattr(today, field)
            - getattr(yesterday, field)
            for field in fields
        }

    return {
        "today": today,
        "yesterday": yesterday,
        "deltas": deltas,
        "has_comparison": bool(today and yesterday),
    }


def safe_percentage(numerator, denominator) -> float:
    """
    Calculate a percentage without raising division errors.
    """

    if not denominator:
        return 0.0

    return round((numerator / denominator) * 100, 2)


def classify_video_length(duration: int) -> str:
    """
    Place a video into a simple duration category.
    """

    if duration <= 0:
        return "Unknown"

    if duration <= 15:
        return "0–15 seconds"

    if duration <= 30:
        return "16–30 seconds"

    if duration <= 60:
        return "31–60 seconds"

    return "Over 60 seconds"


def build_video_metrics(video: TikTokVideo) -> dict:
    """
    Return calculated metrics for one video.
    """

    engagement_count = (
        video.like_count
        + video.comment_count
        + video.share_count
    )

    engagement_rate = safe_percentage(
        engagement_count,
        video.view_count,
    )

    like_rate = safe_percentage(
        video.like_count,
        video.view_count,
    )

    comment_rate = safe_percentage(
        video.comment_count,
        video.view_count,
    )

    share_rate = safe_percentage(
        video.share_count,
        video.view_count,
    )

    return {
        "video": video,
        "engagement_count": engagement_count,
        "engagement_rate": engagement_rate,
        "like_rate": like_rate,
        "comment_rate": comment_rate,
        "share_rate": share_rate,
    }


def calculate_length_performance(videos) -> list[dict]:
    """
    Compare performance between different video lengths.
    """

    groups = defaultdict(list)

    for video in videos:
        length_group = classify_video_length(
            video.duration
        )

        if length_group == "Unknown":
            continue

        groups[length_group].append(video)

    results = []

    for label, group_videos in groups.items():
        average_views = mean(
            video.view_count
            for video in group_videos
        )

        average_engagement = mean(
            safe_percentage(
                (
                    video.like_count
                    + video.comment_count
                    + video.share_count
                ),
                video.view_count,
            )
            for video in group_videos
        )

        results.append(
            {
                "label": label,
                "video_count": len(group_videos),
                "average_views": round(
                    average_views,
                    2,
                ),
                "average_engagement_rate": round(
                    average_engagement,
                    2,
                ),
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["average_views"],
            item["average_engagement_rate"],
        ),
        reverse=True,
    )


def calculate_day_performance(videos) -> list[dict]:
    """
    Compare video performance by publishing weekday.
    """

    groups = defaultdict(list)

    for video in videos:
        if not video.posted_at:
            continue

        day_name = video.posted_at.strftime("%A")
        groups[day_name].append(video)

    results = []

    for day_name, group_videos in groups.items():
        average_views = mean(
            video.view_count
            for video in group_videos
        )

        average_engagement = mean(
            safe_percentage(
                (
                    video.like_count
                    + video.comment_count
                    + video.share_count
                ),
                video.view_count,
            )
            for video in group_videos
        )

        results.append(
            {
                "day": day_name,
                "video_count": len(group_videos),
                "average_views": round(
                    average_views,
                    2,
                ),
                "average_engagement_rate": round(
                    average_engagement,
                    2,
                ),
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["average_views"],
            item["average_engagement_rate"],
        ),
        reverse=True,
    )


def generate_recommendations(
    account: TikTokAccount,
    videos: list[TikTokVideo],
    average_views: float,
    engagement_rate: float,
    length_performance: list[dict],
    day_performance: list[dict],
    top_video_metrics: list[dict],
) -> list[dict]:
    """
    Generate rule-based recommendations from the account's data.
    """

    recommendations = []

    if not videos:
        return [
            {
                "title": "Synchronize your videos",
                "message": (
                    "No public videos are available for analysis. "
                    "Synchronize the account after granting the "
                    "video.list permission."
                ),
                "priority": "high",
            }
        ]

    if length_performance:
        best_length = length_performance[0]

        recommendations.append(
            {
                "title": "Use your strongest video length",
                "message": (
                    f"Your {best_length['label']} videos currently "
                    f"average {best_length['average_views']:,.0f} views. "
                    "Create more videos within this duration range."
                ),
                "priority": "high",
            }
        )

    if day_performance:
        best_day = day_performance[0]

        recommendations.append(
            {
                "title": f"Prioritize {best_day['day']}",
                "message": (
                    f"Videos published on {best_day['day']} currently "
                    f"average {best_day['average_views']:,.0f} views "
                    f"and {best_day['average_engagement_rate']:.2f}% "
                    "engagement."
                ),
                "priority": "medium",
            }
        )

    if account.follower_count and average_views:
        follower_view_ratio = safe_percentage(
            average_views,
            account.follower_count,
        )

        if follower_view_ratio >= 100:
            message = (
                "Your average video reaches at least as many viewers "
                "as your current follower count. Your content is being "
                "discovered beyond your existing audience."
            )
        elif follower_view_ratio >= 50:
            message = (
                "Your average views equal at least half of your follower "
                "count. Strengthen hooks and shares to increase discovery."
            )
        else:
            message = (
                "Your average views are low compared with your follower "
                "count. Test stronger first-second hooks, shorter openings "
                "and clearer video topics."
            )

        recommendations.append(
            {
                "title": "Improve audience reach",
                "message": message,
                "priority": "high",
            }
        )

    if engagement_rate < 3:
        recommendations.append(
            {
                "title": "Increase viewer interaction",
                "message": (
                    "Your overall engagement rate is below 3%. End videos "
                    "with one clear question or invitation to comment, save "
                    "or share."
                ),
                "priority": "high",
            }
        )
    elif engagement_rate < 7:
        recommendations.append(
            {
                "title": "Turn engagement into shares",
                "message": (
                    "Your engagement is healthy. Create useful checklists, "
                    "mistake-based videos and quick tutorials that viewers "
                    "will want to share or save."
                ),
                "priority": "medium",
            }
        )
    else:
        recommendations.append(
            {
                "title": "Repeat your winning format",
                "message": (
                    "Your account has strong engagement. Reuse the format, "
                    "structure and subject of your best-performing videos "
                    "as a recurring series."
                ),
                "priority": "medium",
            }
        )

    if top_video_metrics:
        strongest = top_video_metrics[0]
        video = strongest["video"]

        subject = (
            video.title
            or video.description
            or "your strongest-performing topic"
        )

        recommendations.append(
            {
                "title": "Create a follow-up video",
                "message": (
                    f'Your leading video is "{subject[:100]}". '
                    "Create a sequel, updated version, response video or "
                    "part two using a similar opening."
                ),
                "priority": "high",
            }
        )

    high_share_videos = sorted(
        videos,
        key=lambda video: safe_percentage(
            video.share_count,
            video.view_count,
        ),
        reverse=True,
    )

    if high_share_videos:
        most_shared = high_share_videos[0]

        if most_shared.share_count:
            recommendations.append(
                {
                    "title": "Study your most shareable content",
                    "message": (
                        "Your highest share-rate video should guide future "
                        "educational, relatable or problem-solving content. "
                        "Reuse its structure rather than copying it exactly."
                    ),
                    "priority": "medium",
                }
            )

    return recommendations[:6]


def get_account_analytics(
    account: TikTokAccount,
) -> dict:
    """
    Build the complete analytics package for one account.
    """

    video_queryset = account.videos.all()

    aggregate = video_queryset.aggregate(
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

    videos = list(
        video_queryset.order_by(
            "-view_count",
            "-like_count",
        )
    )

    total_views = aggregate["total_views"] or 0
    total_likes = aggregate["total_likes"] or 0
    total_comments = aggregate["total_comments"] or 0
    total_shares = aggregate["total_shares"] or 0

    total_engagement = (
        total_likes
        + total_comments
        + total_shares
    )

    overall_engagement_rate = safe_percentage(
        total_engagement,
        total_views,
    )

    average_views = round(
        aggregate["average_views"] or 0,
        2,
    )

    top_video_metrics = [
        build_video_metrics(video)
        for video in videos[:5]
    ]

    recent_video_metrics = [
        build_video_metrics(video)
        for video in sorted(
            videos,
            key=lambda item: (
                item.posted_at is not None,
                item.posted_at,
            ),
            reverse=True,
        )[:6]
    ]

    length_performance = calculate_length_performance(
        videos
    )

    day_performance = calculate_day_performance(
        videos
    )

    recommendations = generate_recommendations(
        account=account,
        videos=videos,
        average_views=average_views,
        engagement_rate=overall_engagement_rate,
        length_performance=length_performance,
        day_performance=day_performance,
        top_video_metrics=top_video_metrics,
    )

    return {
        "videos_analyzed": (
            aggregate["videos_analyzed"] or 0
        ),
        "total_views": total_views,
        "total_video_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_engagement": total_engagement,
        "average_views": average_views,
        "average_likes": round(
            aggregate["average_likes"] or 0,
            2,
        ),
        "average_comments": round(
            aggregate["average_comments"] or 0,
            2,
        ),
        "average_shares": round(
            aggregate["average_shares"] or 0,
            2,
        ),
        "highest_views": (
            aggregate["highest_views"] or 0
        ),
        "overall_engagement_rate": (
            overall_engagement_rate
        ),
        "views_per_follower": safe_percentage(
            average_views,
            account.follower_count,
        ),
        "top_videos": top_video_metrics,
        "recent_videos": recent_video_metrics,
        "length_performance": length_performance,
        "day_performance": day_performance,
        "recommendations": recommendations,
    }
