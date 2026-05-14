"""Tests for the classifier pipeline.

``run_classification`` is tested via a thin wrapper (``_run_with_comments``)
that bypasses ``iter_comments`` / ``archive_path`` and feeds a list of
``Comment`` objects directly. This keeps the tests fast and decoupled from
the archive-parsing layer.

``FakeProvider`` is the stand-in for any ``LLMProvider``. It accepts a
``scores`` mapping keyed by comment id; if a comment id isn't in the map it
raises, simulating a parse failure. This lets each test declare exactly
which comments should succeed, which should fail, and with what scores.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest

from rich.progress import Progress

from tidder.classifier import _classify_one, _producer, _worker, run_classification
from tidder.llm.base import LLMProvider
from tidder.models import Classification, Comment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _comment(id: str, body: str = "test body", subreddit: str = "python") -> Comment:
    return Comment(
        id=id,
        url=f"https://reddit.com/r/{subreddit}/comments/{id}",
        body=body,
        subreddit=subreddit,
        created=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


class FakeProvider(LLMProvider):
    """Returns pre-canned scores keyed by comment id. Raises on unknown ids."""

    def __init__(
        self,
        scores: dict[str, dict[int, float]],
        *,
        fail_ids: set[str] | None = None,
    ) -> None:
        self._scores = scores
        # fail_ids always raises regardless of scores map — for retry tests.
        self._fail_ids = fail_ids or set()
        self.call_counts: dict[str, int] = {}

    async def classify(self, comment_body: str, buckets: list[str]) -> dict[int, float]:
        # Body is used as the key in classify; we track by body for simplicity.
        self.call_counts[comment_body] = self.call_counts.get(comment_body, 0) + 1
        if comment_body in self._fail_ids:
            raise ValueError(f"Simulated failure for: {comment_body!r}")
        if comment_body not in self._scores:
            raise ValueError(f"FakeProvider has no scores for body: {comment_body!r}")
        return self._scores[comment_body]

    async def generate_replacement(self, subreddit: str) -> str:
        return "Fake replacement text."


async def _run_with_comments(
    comments: list[Comment],
    provider: LLMProvider,
    buckets: list[str] = ["bucket_a", "bucket_b"],
    *,
    concurrency: int = 2,
    confidence_threshold: float = 0.75,
    retry_threshold: int = 3,
) -> list[Classification]:
    """Run the full queue/worker pipeline against a pre-built comment list."""
    queue: asyncio.Queue[Comment | None] = asyncio.Queue(maxsize=concurrency * 5)
    results: list[Classification] = []

    with Progress(disable=True) as progress:
        task_id = progress.add_task("test", total=len(comments), flagged=0, errored=0)
        await asyncio.gather(
            _producer(iter(comments), queue, concurrency),
            *[
                _worker(
                    queue, results, provider, buckets,
                    confidence_threshold, retry_threshold,
                    progress, task_id,
                )
                for _ in range(concurrency)
            ],
        )
    return results


# ---------------------------------------------------------------------------
# _classify_one
# ---------------------------------------------------------------------------


async def test_classify_one_returns_scores_on_success():
    comment = _comment("c1", body="hello")
    provider = FakeProvider({"hello": {0: 0.9, 1: 0.1}})
    scores = await _classify_one(comment, provider, ["a", "b"], retry_threshold=3)
    assert scores == {0: 0.9, 1: 0.1}


async def test_classify_one_retries_on_failure_then_succeeds():
    """Fails twice, succeeds on the third attempt."""
    call_count = 0
    comment = _comment("c1", body="flaky")

    class FlakyProvider(LLMProvider):
        async def classify(self, body: str, buckets: list[str]) -> dict[int, float]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return {0: 0.8}

        async def generate_replacement(self, subreddit: str) -> str:
            return ""

    scores = await _classify_one(comment, FlakyProvider(), ["a"], retry_threshold=3)
    assert scores == {0: 0.8}
    assert call_count == 3


async def test_classify_one_exhausts_retries_and_raises():
    comment = _comment("c1", body="always_fails")
    provider = FakeProvider({}, fail_ids={"always_fails"})
    with pytest.raises(ValueError, match="Exhausted 3 retries"):
        await _classify_one(comment, provider, ["a"], retry_threshold=3)


async def test_classify_one_retry_threshold_zero_raises_immediately():
    comment = _comment("c1", body="body")
    provider = FakeProvider({})
    with pytest.raises(ValueError, match="Exhausted 0 retries"):
        await _classify_one(comment, provider, ["a"], retry_threshold=0)


# ---------------------------------------------------------------------------
# _producer
# ---------------------------------------------------------------------------


async def test_producer_enqueues_all_comments_then_sentinels():
    comments = [_comment(str(i)) for i in range(5)]
    queue: asyncio.Queue[Comment | None] = asyncio.Queue()
    await _producer(iter(comments), queue, concurrency=3)

    items = []
    while not queue.empty():
        items.append(await queue.get())

    non_sentinel = [i for i in items if i is not None]
    sentinels = [i for i in items if i is None]

    assert len(non_sentinel) == 5
    assert len(sentinels) == 3  # one per worker


async def test_producer_empty_iterator_sends_only_sentinels():
    queue: asyncio.Queue[Comment | None] = asyncio.Queue()
    await _producer(iter([]), queue, concurrency=2)

    items = []
    while not queue.empty():
        items.append(await queue.get())

    assert all(i is None for i in items)
    assert len(items) == 2


# ---------------------------------------------------------------------------
# run_classification (full pipeline via _run_with_comments)
# ---------------------------------------------------------------------------


async def test_pipeline_flags_comments_above_threshold():
    comments = [
        _comment("high", body="high"),
        _comment("low", body="low"),
    ]
    provider = FakeProvider({
        "high": {0: 0.9, 1: 0.1},  # max=0.9, above 0.75
        "low":  {0: 0.2, 1: 0.3},  # max=0.3, below 0.75
    })
    results = await _run_with_comments(comments, provider, confidence_threshold=0.75)

    ids = {r.comment.id for r in results if not r.errored}
    assert ids == {"high"}
    assert len(results) == 1


async def test_pipeline_errored_comment_always_included():
    comments = [
        _comment("good", body="good"),
        _comment("bad", body="bad"),
    ]
    provider = FakeProvider(
        {"good": {0: 0.9, 1: 0.1}},
        fail_ids={"bad"},
    )
    results = await _run_with_comments(comments, provider, retry_threshold=1)

    errored = [r for r in results if r.errored]
    flagged = [r for r in results if not r.errored]

    assert len(errored) == 1
    assert errored[0].comment.id == "bad"
    assert errored[0].scores is None
    assert len(flagged) == 1
    assert flagged[0].comment.id == "good"


async def test_pipeline_empty_archive_returns_empty():
    provider = FakeProvider({})
    results = await _run_with_comments([], provider)
    assert results == []


async def test_pipeline_all_below_threshold_returns_only_errors():
    comments = [_comment(str(i), body=str(i)) for i in range(3)]
    provider = FakeProvider({str(i): {0: 0.1, 1: 0.2} for i in range(3)})
    results = await _run_with_comments(comments, provider, confidence_threshold=0.75)
    assert results == []


async def test_pipeline_threshold_boundary_exact_match_is_included():
    comments = [_comment("exact", body="exact")]
    provider = FakeProvider({"exact": {0: 0.75, 1: 0.1}})
    results = await _run_with_comments(comments, provider, confidence_threshold=0.75)
    assert len(results) == 1
    assert results[0].comment.id == "exact"


async def test_pipeline_scores_stored_correctly():
    comments = [_comment("c1", body="c1")]
    provider = FakeProvider({"c1": {0: 0.88, 1: 0.42}})
    results = await _run_with_comments(comments, provider, confidence_threshold=0.5)
    assert results[0].scores == {0: 0.88, 1: 0.42}
    assert results[0].errored is False
    assert results[0].error_message is None


async def test_pipeline_concurrency_respected():
    """All comments classified regardless of concurrency setting."""
    n = 20
    comments = [_comment(str(i), body=str(i)) for i in range(n)]
    provider = FakeProvider({str(i): {0: 0.9} for i in range(n)})
    results = await _run_with_comments(
        comments, provider, buckets=["a"], concurrency=5, confidence_threshold=0.5
    )
    assert len(results) == n


async def test_pipeline_error_message_captured():
    comments = [_comment("fail", body="fail")]
    provider = FakeProvider({}, fail_ids={"fail"})
    results = await _run_with_comments(comments, provider, retry_threshold=1)
    assert results[0].errored is True
    assert "fail" in results[0].error_message
