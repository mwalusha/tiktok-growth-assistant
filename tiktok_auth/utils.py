import re


HASHTAG_PATTERN = re.compile(r"(?<!\w)#([\w]+)", re.UNICODE)


def extract_hashtags(description: str) -> list[str]:
    """Extract unique, normalized hashtags in caption order."""

    hashtags = []
    seen = set()
    for match in HASHTAG_PATTERN.finditer(description or ""):
        hashtag = match.group(1).casefold()
        if hashtag not in seen:
            seen.add(hashtag)
            hashtags.append(hashtag)
    return hashtags


TOPIC_KEYWORDS = {
    "transformation": (
        "before and after", "transformation", "makeover", "glow up",
    ),
    "tutorial": (
        "tutorial", "how to", "step by step", "guide", "tips",
    ),
    "client reaction": (
        "reaction", "first look", "saw the result", "mirror reveal",
    ),
    "client story": (
        "client", "appointment", "customer", "she wanted", "he wanted",
    ),
    "storytelling": (
        "story time", "storytime", "what happened", "lesson learned",
    ),
    "product review": (
        "product", "review", "unboxing", "recommend", "routine",
    ),
    "behind the scenes": (
        "behind the scenes", "bts", "day in the life", "process",
    ),
    "lifestyle": (
        "lifestyle", "morning routine", "weekly vlog", "get ready with me",
    ),
    "trend": (
        "trend", "challenge", "viral sound", "duet", "stitch",
    ),
    "question and answer": (
        "q&a", "question", "answering", "you asked", "faq",
    ),
}


def classify_topic(text: str) -> str:
    normalized = (text or "").casefold()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return topic
    return "other"
