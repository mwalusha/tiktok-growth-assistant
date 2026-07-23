from datetime import date, timedelta
from statistics import pstdev

from django.utils import timezone


SCORE_WEIGHTS = {
    "posting_consistency": 0.25,
    "engagement_trend": 0.30,
    "follower_growth": 0.25,
    "activity": 0.20,
}
COMPONENT_LABELS = {
    "posting_consistency": "posting consistency",
    "engagement_trend": "engagement momentum",
    "follower_growth": "follower growth",
    "activity": "recent activity",
}


def clamp(value: float, minimum=0.0, maximum=100.0) -> float:
    return max(minimum, min(maximum, value))


def _posted_date(video):
    return video.posted_at.date() if video.posted_at else None


def posting_consistency_score(
    videos,
    as_of: date,
) -> float:
    """Score variation in gaps between posts over the preceding 30 days."""

    start = as_of - timedelta(days=29)
    posting_dates = sorted(
        {
            posted_date
            for video in videos
            if (posted_date := _posted_date(video))
            and start <= posted_date <= as_of
        }
    )

    if not posting_dates:
        return 0.0

    if len(posting_dates) == 1:
        return 25.0

    if len(posting_dates) == 2:
        return 50.0

    gaps = [
        (current - previous).days
        for previous, current in zip(
            posting_dates,
            posting_dates[1:],
        )
    ]
    # A perfectly regular schedule scores 100. Each day of standard
    # deviation costs 12.5 points.
    return clamp(100.0 - pstdev(gaps) * 12.5)


def _linear_slope(points: list[tuple[int, float]]) -> float:
    if len(points) < 2:
        return 0.0

    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    denominator = sum(
        (x - mean_x) ** 2 for x, _ in points
    )

    if not denominator:
        return 0.0

    return sum(
        (x - mean_x) * (y - mean_y)
        for x, y in points
    ) / denominator


def engagement_trend_score(
    snapshots,
    as_of: date,
) -> float:
    """
    Score the 14-day engagement-rate slope.

    Flat engagement is neutral at 50; each percentage point gained per
    day adds 10 points, and declines subtract at the same rate.
    """

    start = as_of - timedelta(days=13)
    window = [
        snapshot
        for snapshot in snapshots
        if start <= snapshot.date <= as_of
    ]

    if len(window) < 2:
        return 50.0

    points = [
        (
            (snapshot.date - start).days,
            float(snapshot.avg_engagement_rate),
        )
        for snapshot in window
    ]
    return clamp(50.0 + _linear_slope(points) * 10.0)


def _latest_snapshot_on_or_before(snapshots, boundary):
    eligible = [
        snapshot
        for snapshot in snapshots
        if snapshot.date <= boundary
        and snapshot.date >= boundary - timedelta(days=2)
    ]
    return max(eligible, key=lambda item: item.date, default=None)


def _percentage_growth(start_value, end_value) -> float:
    if not start_value:
        return 0.0

    return (end_value - start_value) / start_value * 100.0


def follower_growth_score(
    snapshots,
    as_of: date,
) -> float:
    """
    Compare follower growth in the last seven days with the prior seven.
    """

    current = _latest_snapshot_on_or_before(
        snapshots,
        as_of,
    )
    middle = _latest_snapshot_on_or_before(
        snapshots,
        as_of - timedelta(days=7),
    )
    start = _latest_snapshot_on_or_before(
        snapshots,
        as_of - timedelta(days=14),
    )

    if not current or not middle or not start:
        return 50.0

    prior_growth = _percentage_growth(
        start.follower_count,
        middle.follower_count,
    )
    current_growth = _percentage_growth(
        middle.follower_count,
        current.follower_count,
    )
    # Neutral means the current week matches the prior week. Ten score
    # points are awarded per percentage point of acceleration.
    return clamp(
        50.0 + (current_growth - prior_growth) * 10.0
    )


def activity_score(
    videos,
    as_of: date,
) -> float:
    """
    Score post recency and seven-day publishing activity.

    TikTok's video list does not expose creator-reply events, so posting
    frequency is the explicit activity proxy until that data is available.
    """

    eligible_dates = [
        posted_date
        for video in videos
        if (posted_date := _posted_date(video))
        and posted_date <= as_of
    ]

    if not eligible_dates:
        return 0.0

    days_since_last_post = (
        as_of - max(eligible_dates)
    ).days
    recency = clamp(
        100.0 - days_since_last_post * 12.5
    )
    week_start = as_of - timedelta(days=6)
    active_days = len(
        {
            posted_date
            for posted_date in eligible_dates
            if posted_date >= week_start
        }
    )
    frequency = clamp(active_days / 4.0 * 100.0)
    return recency * 0.70 + frequency * 0.30


def _component_scores(videos, snapshots, as_of):
    return {
        "posting_consistency": posting_consistency_score(
            videos,
            as_of,
        ),
        "engagement_trend": engagement_trend_score(
            snapshots,
            as_of,
        ),
        "follower_growth": follower_growth_score(
            snapshots,
            as_of,
        ),
        "activity": activity_score(videos, as_of),
    }


def _weighted_total(components) -> float:
    return sum(
        SCORE_WEIGHTS[name] * value
        for name, value in components.items()
    )


def build_score_explanations(current, previous) -> list[dict]:
    changes = []

    for name, weight in SCORE_WEIGHTS.items():
        point_change = weight * (
            current[name] - previous[name]
        )

        if abs(point_change) < 0.5:
            continue

        direction = "improved" if point_change > 0 else "declined"
        signed_points = round(point_change)
        changes.append(
            {
                "component": name,
                "points": signed_points,
                "text": (
                    f"{signed_points:+d} points because "
                    f"{COMPONENT_LABELS[name]} {direction}."
                ),
            }
        )

    changes.sort(
        key=lambda item: abs(item["points"]),
        reverse=True,
    )

    if not changes:
        return [
            {
                "component": "overall",
                "points": 0,
                "text": (
                    "Your score held steady because this week's "
                    "component scores are close to last week's."
                ),
            }
        ]

    return changes


def get_creator_score(account, as_of=None) -> dict:
    """Calculate the weighted score and week-over-week explanation."""

    as_of = as_of or timezone.localdate()
    oldest_date = as_of - timedelta(days=37)
    videos = list(
        account.videos.filter(
            posted_at__date__gte=oldest_date,
            posted_at__date__lte=as_of,
        )
    )
    snapshots = list(
        account.daily_snapshots.filter(
            date__gte=as_of - timedelta(days=21),
            date__lte=as_of,
        )
    )
    current = _component_scores(
        videos,
        snapshots,
        as_of,
    )
    previous = _component_scores(
        videos,
        snapshots,
        as_of - timedelta(days=7),
    )
    total = _weighted_total(current)
    previous_total = _weighted_total(previous)

    return {
        "score": round(total),
        "score_exact": round(total, 2),
        "previous_score": round(previous_total),
        "change": round(total) - round(previous_total),
        "components": {
            name: round(value, 1)
            for name, value in current.items()
        },
        "previous_components": {
            name: round(value, 1)
            for name, value in previous.items()
        },
        "explanations": build_score_explanations(
            current,
            previous,
        ),
    }
