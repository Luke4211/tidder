"""Column definitions for tidder's output CSVs."""

from __future__ import annotations

FLAGGED_COLUMNS = (
    "id",
    "url",
    "confidence_mapping",
    "comment_text",
    "comment_date",
    "subreddit",
    "flagged_for_del",
)

ERRORED_COLUMNS = (
    "id",
    "url",
    "comment_text",
    "comment_date",
    "error_message",
)

SAMPLE_COLUMNS = (
    "id",
    "permalink",
    "body",
    "subreddit",
    "date",
)


def format_confidence_mapping(scores: dict[int, float]) -> str:
    """Render a ``{bucket_index: score}`` mapping as ``0:0.92,1:0.10``."""
    return ",".join(f"{idx}:{score:.2f}" for idx, score in sorted(scores.items()))
