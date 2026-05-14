"""Shared data shapes used across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Comment:
    """A single Reddit comment as read from the export archive."""

    id: str
    url: str
    body: str
    subreddit: str
    created: datetime
    score: int | None = None


@dataclass(slots=True)
class Classification:
    """Result of running one comment through the classifier."""

    comment: Comment
    scores: dict[int, float]
    errored: bool = False
    error_message: str | None = None

    @property
    def max_score(self) -> float:
        return max(self.scores.values()) if self.scores else 0.0


@dataclass(slots=True)
class RunMetadata:
    """Captured alongside each output bundle for traceability."""

    started_at: datetime
    finished_at: datetime | None
    source_archive: str
    llm_provider: str
    llm_model: str
    llm_host: str
    confidence_threshold: float
    retry_threshold: int
    concurrency: int
    buckets: list[str] = field(default_factory=list)
