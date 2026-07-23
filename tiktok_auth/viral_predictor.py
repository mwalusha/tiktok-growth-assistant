import re
from math import ceil, floor


HASHTAG_PATTERN = re.compile(r"(?<!\w)#([\w]+)")
FACTOR_WEIGHTS = {
    "caption_length": 0.45,
    "hashtag_count": 0.35,
    "trending_hashtags": 0.20,
}


class ViralPredictionError(Exception):
    """Raised when an account has too little history to score a draft."""


def _percentile(values, percentile):
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = floor(position)
    upper = ceil(position)

    if lower == upper:
        return ordered[lower]

    return (
        ordered[lower] * (upper - position)
        + ordered[upper] * (position - lower)
    )


def _optimal_range(values) -> tuple[int, int]:
    return (
        round(_percentile(values, 0.25)),
        round(_percentile(values, 0.75)),
    )


def _range_score(value, optimal_min, optimal_max) -> float:
    if optimal_min <= value <= optimal_max:
        return 100.0

    distance = (
        optimal_min - value
        if value < optimal_min
        else value - optimal_max
    )
    scale = max(optimal_max - optimal_min, optimal_max, 1)
    return max(0.0, 100.0 - distance / scale * 100.0)


def _hashtags(value):
    return [
        match.group(1).casefold()
        for match in HASHTAG_PATTERN.finditer(value or "")
    ]


def score_draft(
    account,
    caption: str,
    hashtags: str,
    trending_hashtags=None,
) -> dict:
    """Compare a draft with this account's highest-viewed patterns."""

    top_videos = list(
        account.videos.order_by("-view_count")[:10]
    )

    if len(top_videos) < 3:
        raise ViralPredictionError(
            "Synchronize at least three videos before scoring a draft."
        )

    caption_lengths = [
        len(video.description or video.title or "")
        for video in top_videos
    ]
    hashtag_counts = [
        len(video.hashtags or [])
        for video in top_videos
    ]
    caption_range = _optimal_range(caption_lengths)
    hashtag_range = _optimal_range(hashtag_counts)
    draft_hashtags = _hashtags(hashtags)
    components = {
        "caption_length": _range_score(
            len(caption.strip()),
            *caption_range,
        ),
        "hashtag_count": _range_score(
            len(draft_hashtags),
            *hashtag_range,
        ),
    }
    available_weights = {
        "caption_length": FACTOR_WEIGHTS["caption_length"],
        "hashtag_count": FACTOR_WEIGHTS["hashtag_count"],
    }
    trending_matches = []
    trending_available = trending_hashtags is not None

    if trending_available:
        normalized_trending = {
            hashtag.lstrip("#").casefold()
            for hashtag in trending_hashtags
        }
        trending_matches = sorted(
            set(draft_hashtags) & normalized_trending
        )
        components["trending_hashtags"] = (
            100.0 if trending_matches else 0.0
        )
        available_weights["trending_hashtags"] = (
            FACTOR_WEIGHTS["trending_hashtags"]
        )

    weight_total = sum(available_weights.values())
    score = sum(
        components[name] * weight
        for name, weight in available_weights.items()
    ) / weight_total
    explanations = [
        (
            f"Your caption has {len(caption.strip())} characters; "
            f"your strongest historical range is "
            f"{caption_range[0]}–{caption_range[1]}."
        ),
        (
            f"Your draft has {len(draft_hashtags)} hashtags; "
            f"your strongest historical range is "
            f"{hashtag_range[0]}–{hashtag_range[1]}."
        ),
    ]

    if trending_available:
        explanations.append(
            "Trending hashtag match: "
            + (
                ", ".join(f"#{tag}" for tag in trending_matches)
                if trending_matches
                else "none"
            )
            + "."
        )
    else:
        explanations.append(
            "Trending hashtag data is unavailable until Phase 9; "
            "this factor was excluded and the available factors were "
            "reweighted."
        )

    return {
        "score": round(score),
        "score_exact": round(score, 2),
        "label": (
            "Strong historical fit"
            if score >= 75
            else "Moderate historical fit"
            if score >= 50
            else "Weak historical fit"
        ),
        "based_on_videos": len(top_videos),
        "components": {
            key: round(value, 1)
            for key, value in components.items()
        },
        "caption_range": caption_range,
        "hashtag_range": hashtag_range,
        "trending_available": trending_available,
        "trending_matches": trending_matches,
        "explanations": explanations,
        "disclaimer": (
            "Based on your history, not a guarantee of future reach."
        ),
    }
