"""The ``process`` pipeline core.

Pulls comments from an archive, fans them out across an async worker pool
against an ``LLMProvider``, retries parse / range failures up to a threshold,
and collects the results. Sorting, filtering by confidence threshold, and
bundling are deferred to the caller / IO layer.
"""

from __future__ import annotations

from pathlib import Path

from .llm.base import LLMProvider
from .models import Classification


async def run_classification(
    archive_path: Path,
    buckets: list[str],
    provider: LLMProvider,
    *,
    concurrency: int,
    retry_threshold: int,
) -> list[Classification]:
    """Classify every comment in ``archive_path`` against ``buckets``. Stub."""
    raise NotImplementedError("classifier.run_classification is not implemented yet.")
