"""Abstract LLM provider interface.

A provider knows how to do two things for tidder:

1. Classify a comment against a set of user-supplied buckets, returning a
   confidence score per bucket.
2. Generate a generic, politically-neutral, plausible-sounding replacement
   comment used by ``remove --overwrite-style llm``.

Every concrete provider must use a *fresh context window* per call. Calls
across comments must not influence each other.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interface every LLM backend must implement."""

    @abstractmethod
    async def classify(
        self,
        comment_body: str,
        buckets: list[str],
    ) -> dict[int, float]:
        """Return ``{bucket_index: confidence_score}`` for all buckets.

        Scores must lie in ``[0.0, 1.0]``. Implementations should raise on
        parse failure / out-of-range output so the surrounding retry loop can
        decide what to do.
        """

    @abstractmethod
    async def generate_replacement(self, subreddit: str) -> str:
        """Generate a generic, neutral replacement body for an overwrite.

        Takes the subreddit as light context (so the replacement reads as
        plausible for that community) but deliberately does *not* see the
        original comment body — anchoring on the original would defeat the
        privacy goal.
        """

    async def aclose(self) -> None:
        """Release any underlying network resources. Default: no-op."""
        return None
