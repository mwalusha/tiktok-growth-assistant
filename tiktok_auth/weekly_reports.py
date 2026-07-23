from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .creator_score import get_creator_score
from .models import WeeklyReport


RECOMMENDATIONS = {
    "posting_consistency": (
        "Choose a repeatable posting cadence next week and protect those "
        "publishing slots."
    ),
    "engagement_trend": (
        "Reuse the hook and format from your strongest recent video, then "
        "end with one clear prompt to comment or share."
    ),
    "follower_growth": (
        "Create a follow-up to your most-viewed topic and make the value "
        "for new viewers clear in the first sentence."
    ),
    "activity": (
        "Publish again soon and aim for at least four active posting days "
        "during the coming week."
    ),
}
DELTA_FIELDS = (
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


def previous_completed_week(today=None):
    today = today or timezone.localdate()
    current_monday = today - timedelta(
        days=today.weekday()
    )
    return current_monday - timedelta(days=7)


def _snapshot_deltas(snapshots):
    if not snapshots:
        return {}

    first = snapshots[0]
    last = snapshots[-1]
    return {
        field: float(getattr(last, field))
        - float(getattr(first, field))
        for field in DELTA_FIELDS
    }


@transaction.atomic
def generate_weekly_report(account, week_start=None):
    week_start = week_start or previous_completed_week()
    week_end = week_start + timedelta(days=6)
    snapshots = list(
        account.daily_snapshots.filter(
            date__range=(week_start, week_end)
        ).order_by("date")
    )
    videos = account.videos.filter(
        posted_at__date__range=(week_start, week_end)
    )
    best_video = videos.order_by(
        "-view_count",
        "-like_count",
    ).first()
    worst_video = videos.order_by(
        "view_count",
        "like_count",
    ).first()
    score = get_creator_score(account, as_of=week_end)
    weakest_component = min(
        score["components"],
        key=score["components"].get,
    )
    report, created = WeeklyReport.objects.update_or_create(
        account=account,
        week_start=week_start,
        defaults={
            "week_end": week_end,
            "snapshot_deltas": _snapshot_deltas(snapshots),
            "creator_score": score["score"],
            "creator_sub_scores": score["components"],
            "recommendation": RECOMMENDATIONS[
                weakest_component
            ],
            "best_video": best_video,
            "worst_video": worst_video,
        },
    )
    return report, created
