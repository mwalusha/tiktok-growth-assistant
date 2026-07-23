from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    FloatField,
)
from django.db.models.functions import (
    ExtractHour,
    ExtractWeekDay,
)


DAY_NAMES = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
    7: "Saturday",
}
CONFIDENCE_POST_TARGET = 5


def format_hour(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:00 {suffix}"


def confidence_for_sample_size(sample_size: int) -> dict:
    """
    Convert bucket size to a transparent confidence score.

    Each historical post contributes 20 points, capped at five posts.
    """

    score = min(
        100,
        round(
            sample_size
            / CONFIDENCE_POST_TARGET
            * 100
        ),
    )

    if score >= 80:
        label = "High"
    elif score >= 40:
        label = "Medium"
    else:
        label = "Low"

    return {
        "score": score,
        "label": label,
    }


def get_best_posting_times(account, limit=5) -> dict:
    """
    Rank posting slots with one grouped SQL query.

    Engagement follows the product definition: average likes plus average
    comments plus average shares for each UTC weekday/hour bucket.
    """

    average_engagement = ExpressionWrapper(
        Avg("like_count")
        + Avg("comment_count")
        + Avg("share_count"),
        output_field=FloatField(),
    )
    rows = (
        account.videos.exclude(posted_at__isnull=True)
        .annotate(
            hour=ExtractHour("posted_at"),
            dow=ExtractWeekDay("posted_at"),
        )
        .values("hour", "dow")
        .annotate(
            avg_engagement=average_engagement,
            sample_size=Count("id"),
        )
        .order_by(
            "-avg_engagement",
            "-sample_size",
            "dow",
            "hour",
        )[:limit]
    )
    recommendations = []

    for row in rows:
        confidence = confidence_for_sample_size(
            row["sample_size"]
        )
        recommendations.append(
            {
                "hour": row["hour"],
                "day_of_week": row["dow"],
                "day_name": DAY_NAMES[row["dow"]],
                "time_label": format_hour(row["hour"]),
                "avg_engagement": round(
                    row["avg_engagement"] or 0,
                    1,
                ),
                "sample_size": row["sample_size"],
                "confidence_score": confidence["score"],
                "confidence_label": confidence["label"],
            }
        )

    return {
        "timezone": "UTC",
        "recommendations": recommendations,
        "best": recommendations[0] if recommendations else None,
    }
