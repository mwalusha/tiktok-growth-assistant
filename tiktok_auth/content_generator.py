from .models import ContentIdea


IDEA_PATTERNS = [
    {
        "title": "Watch this full {topic} transformation",
        "hook": "She almost cancelled this appointment…",
        "caption": "The result is worth watching until the end.",
    },
    {
        "title": "Three mistakes people make with {topic}",
        "hook": "If you do this, stop before your next attempt.",
        "caption": "Save this before you try it yourself.",
    },
    {
        "title": "How I approach {topic} step by step",
        "hook": "Here is the part most people skip.",
        "caption": "A simple behind-the-scenes breakdown.",
    },
    {
        "title": "What I would do differently with {topic}",
        "hook": "I wish someone had told me this sooner.",
        "caption": "One lesson that changed my process.",
    },
    {
        "title": "Answering the biggest question about {topic}",
        "hook": "This is the question I get asked most.",
        "caption": "The honest answer, based on real experience.",
    },
    {
        "title": "A quick {topic} result you can copy",
        "hook": "Give me 20 seconds and I will show you how.",
        "caption": "Try this format and tell me how it goes.",
    },
]


def _hashtag_text(analytics):
    topic = (analytics.get("summary", {}).get("top_topic") or "creator")
    tags = [topic.replace(" ", ""), "tiktoktips", "contentideas"]
    return " ".join(f"#{tag}" for tag in tags)


def generate_personalized_content_ideas(
    account, analytics: dict, count: int = 5
) -> list[ContentIdea]:
    """Create deterministic planner ideas from this account's own results."""

    count = max(1, min(int(count), len(IDEA_PATTERNS)))
    summary = analytics.get("summary", {})
    topic = summary.get("top_topic") or account.niche or "your niche"
    length = summary.get("best_length") or "15–20 seconds"
    day = summary.get("best_day") or ""
    time_window = summary.get("best_time") or ""
    posting_time = " ".join(value for value in (day, time_window) if value)
    existing = {
        title.casefold()
        for title in account.content_ideas.values_list("title", flat=True)
    }
    generated = []

    for pattern in IDEA_PATTERNS:
        title = pattern["title"].format(topic=topic)
        if title.casefold() in existing:
            continue
        reason = (
            f"Your {topic} videos are currently your strongest topic"
            if summary.get("top_topic")
            else "This gives you a structured format while more videos sync"
        )
        idea = ContentIdea.objects.create(
            account=account,
            title=title,
            category=ContentIdea.Category.OTHER,
            content_type=ContentIdea.ContentType.EDUCATIONAL,
            hook=pattern["hook"],
            caption=pattern["caption"],
            hashtags=_hashtag_text(analytics),
            status=ContentIdea.Status.DRAFT,
            is_generated=True,
            reason=reason,
            generation_reason=reason,
            suggested_length=length,
            suggested_duration=length,
            suggested_posting_day=day,
            suggested_posting_time=posting_time,
            notes="Generated from your synchronized TikTok performance.",
        )
        generated.append(idea)
        existing.add(title.casefold())
        if len(generated) >= count:
            break
    return generated
