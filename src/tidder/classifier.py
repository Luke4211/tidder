"""The ``process`` pipeline core.

Pulls comments from an archive, fans them out across an async worker pool
against an ``LLMProvider``, retries parse / range failures up to a threshold,
and collects the results. Sorting, filtering by confidence threshold, and
bundling are deferred to the caller / IO layer.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterator

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from .archive import count_comments, iter_comments
from .llm.base import LLMProvider
from .models import Classification, Comment


async def _classify_one(
    comment: Comment, provider: LLMProvider, buckets: list[str], retry_threshold: int
) -> dict[int, float]:

    last_error: Exception | None = None
    for attempt in range(retry_threshold):
        try:
            return await provider.classify(comment.body, buckets)
        except Exception as e:
            last_error = e

    raise ValueError(
        f"Exhausted {retry_threshold} retries for comment {comment.id}: {last_error}"
    )


async def _producer(
    comments: Iterator[Comment], queue: asyncio.Queue[Comment | None], concurrency: int
) -> None:
    for comment in comments:
        await queue.put(comment)

    for _ in range(concurrency):
        await queue.put(None)


async def _worker(
    queue: asyncio.Queue[Comment | None],
    results: list[Classification],
    provider: LLMProvider,
    buckets: list[str],
    confidence_threshold: float,
    retry_threshold: int,
    progress: Progress,
    task_id: TaskID,
):
    while True:
        comment = await queue.get()
        if comment is None:
            return
        try:
            result = await _classify_one(comment, provider, buckets, retry_threshold)
            if max(result.values()) >= confidence_threshold:
                results.append(Classification(comment, result))
                task = progress.tasks[task_id]
                progress.update(task_id, flagged=task.fields["flagged"] + 1)
        except Exception as e:
            results.append(
                Classification(comment, None, errored=True, error_message=str(e))
            )
            task = progress.tasks[task_id]
            progress.update(task_id, errored=task.fields["errored"] + 1)
        finally:
            progress.advance(task_id)


async def run_classification(
    archive_path: Path,
    buckets: list[str],
    provider: LLMProvider,
    *,
    concurrency: int,
    confidence_threshold: float,
    retry_threshold: int,
) -> list[Classification]:
    total = count_comments(archive_path)
    queue: asyncio.Queue[Comment | None] = asyncio.Queue(maxsize=concurrency * 5)
    comments = iter_comments(archive_path)
    results: list[Classification] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[green]flagged: {task.fields[flagged]}[/]"),
        TextColumn("[red]errored: {task.fields[errored]}[/]"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task_id = progress.add_task(
            "Classifying...", total=total, flagged=0, errored=0
        )

        await asyncio.gather(
            _producer(comments, queue, concurrency),
            *[
                _worker(
                    queue,
                    results,
                    provider,
                    buckets,
                    confidence_threshold,
                    retry_threshold,
                    progress,
                    task_id,
                )
                for _ in range(concurrency)
            ],
        )

    return results
