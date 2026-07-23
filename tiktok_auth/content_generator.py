import re

from .models import ContentIdea


def normalize_title(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", (title or "").casefold())
    ignored = {"a", "this", "the", "complete", "full"}
    return " ".join(word for word in words if word not in ignored)


def _subject(video, fallback):
    if not video:
        return fallback
    text = video.title or video.description or fallback
    text = re.sub(r"#\w+", "", text).strip(" .,-")
    return text[:70] or fallback


def _hashtags(topic, source_video):
    tags = []
    for value in [topic, *((source_video.hashtags or []) if source_video else [])]:
        tag = re.sub(r"[^\w]", "", str(value).casefold())
        if tag and tag not in tags:
            tags.append(tag)
    for fallback in ("creatorideas", "tiktoktips"):
        if fallback not in tags:
            tags.append(fallback)
    return " ".join(f"#{tag}" for tag in tags[:5])


def _evidence_reason(analytics, topic_row, length_row, day_row, time_row):
    parts = []
    if topic_row:
        ratio = (
            topic_row["average_views"] / analytics["average_views"]
            if analytics.get("average_views")
            else 0
        )
        parts.append(
            f"Based on {topic_row['video_count']} {topic_row['topic']} "
            f"video{'s' if topic_row['video_count'] != 1 else ''}, averaging "
            f"{topic_row['average_views']:,.0f} views"
            + (f" ({ratio:.1f}× your overall average)" if ratio else "")
        )
    if length_row:
        parts.append(
            f"{length_row['label']} is supported by "
            f"{length_row['video_count']} post"
            f"{'s' if length_row['video_count'] != 1 else ''}"
        )
    if day_row and time_row:
        parts.append(
            f"{day_row['day']} and the {time_row['time']} posting window "
            "are your strongest current timing patterns"
        )
    return ". ".join(parts) + ("." if parts else "")


def _candidate_set(topic, source, weak_topic, repeated_recently):
    subject = _subject(source, topic)
    repeat_title = f"Watch the full {topic} result"
    repeat_hook = "Wait until you see the final result."
    if repeated_recently:
        repeat_title = f"The reaction after the {topic} result"
        repeat_hook = "The transformation was only half the story."
    return [
        {
            "kind": "strongest format",
            "title": repeat_title,
            "hook": repeat_hook,
            "concept": (
                "Open with the starting point, use three fast process clips, "
                "then finish with a clear result and reaction."
            ),
            "topic": topic,
            "source": source,
        },
        {
            "kind": "top-video follow-up",
            "title": f"What happened after {subject}",
            "hook": "You saw the result—here is what happened next.",
            "concept": (
                "Reference the original result, show the follow-up, and answer "
                "the most natural question a viewer would ask next."
            ),
            "topic": topic,
            "source": source,
        },
        {
            "kind": "winning-topic tutorial",
            "title": f"Three steps behind {subject}",
            "hook": "The final result depends on what happens before this.",
            "concept": (
                "Teach three concise steps from the proven topic while using "
                "the finished result as the opening visual."
            ),
            "topic": "tutorial",
            "source": source,
        },
        {
            "kind": "reaction and reveal",
            "title": f"Seeing the {topic} result for the first time",
            "hook": "They had not seen the final result yet…",
            "concept": (
                "Hold back the finished view, capture the first reaction, "
                "then end on a clean reveal."
            ),
            "topic": "client reaction",
            "source": source,
        },
        {
            "kind": "controlled experiment",
            "title": f"Testing {weak_topic} inside a fast {topic}",
            "hook": "This one change made the final result possible.",
            "concept": (
                f"Test {weak_topic} in a short, proven {topic} structure "
                "instead of repeating the weaker long-form presentation."
            ),
            "topic": weak_topic,
            "source": source,
        },
        {
            "kind": "question and answer",
            "title": f"The biggest question about {subject}",
            "hook": "This is what everyone asks after seeing the result.",
            "concept": "Answer one question quickly, then show the evidence.",
            "topic": "question and answer",
            "source": source,
        },
        {
            "kind": "behind the scenes",
            "title": f"What you did not see during {subject}",
            "hook": "The final clip hides the most important part.",
            "concept": "Reveal one useful process detail behind the top post.",
            "topic": "behind the scenes",
            "source": source,
        },
    ]


def generate_personalized_content_ideas(
    account, analytics: dict, count: int = 5
) -> list[ContentIdea]:
    """Save varied ideas whose claims come only from synchronized history."""

    if not analytics.get("videos_analyzed"):
        return []
    count = max(1, min(int(count), 5))
    topic_row = analytics.get("best_topic")
    length_row = analytics.get("best_video_length")
    day_row = analytics.get("best_posting_day")
    time_row = analytics.get("best_posting_time")
    topic = topic_row["topic"] if topic_row else (account.niche or "content")
    weak_rows = analytics.get("weak_topics") or []
    weak_topic = (
        weak_rows[0]["topic"]
        if weak_rows and weak_rows[0]["topic"] != topic
        else "product review"
    )
    source_metric = (analytics.get("top_videos") or [None])[0]
    source = source_metric["video"] if source_metric else None
    repeated_recently = (
        len(analytics.get("last_three_topics") or []) == 3
        and len(set(analytics["last_three_topics"])) == 1
        and analytics["last_three_topics"][0] == topic
    )
    length = length_row["label"] if length_row else ""
    day = day_row["day"] if day_row else ""
    posting_window = time_row["time"] if time_row else ""
    evidence = _evidence_reason(
        analytics, topic_row, length_row, day_row, time_row
    )
    confidence = (
        topic_row["confidence"] if topic_row else "Limited data"
    )
    existing = {
        normalize_title(title)
        for title in account.content_ideas.values_list("title", flat=True)
    }
    generated = []

    for candidate in _candidate_set(
        topic, source, weak_topic, repeated_recently
    ):
        normalized = normalize_title(candidate["title"])
        if normalized in existing:
            continue
        reason = (
            f"{candidate['kind'].title()}: {evidence} "
            f"Confidence: {confidence}."
        ).strip()
        idea = ContentIdea.objects.create(
            account=account,
            title=candidate["title"],
            topic=candidate["topic"],
            category=ContentIdea.Category.OTHER,
            content_type=ContentIdea.ContentType.EDUCATIONAL,
            hook=candidate["hook"],
            concept=candidate["concept"],
            script=candidate["concept"],
            caption="Save this idea and watch through to the final result.",
            hashtags=_hashtags(candidate["topic"], candidate["source"]),
            source_video=candidate["source"],
            status=ContentIdea.Status.DRAFT,
            is_generated=True,
            reason=reason,
            generation_reason=reason,
            confidence=confidence,
            suggested_length=length,
            suggested_duration=length,
            suggested_posting_day=day,
            suggested_posting_time=posting_window,
            notes="Generated only from locally synchronized TikTok history.",
        )
        generated.append(idea)
        existing.add(normalized)
        if len(generated) == count:
            break
    return generated
