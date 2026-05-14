"""Reddit data-export archive parsing.

Reddit's data-export ``.zip`` contains many CSVs; for tidder we care about
``comments.csv`` (and ``comment_headers.csv`` when present, which carries
column names some older exports omit).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .models import Comment

import zipfile
import io


def _row_to_comment(row: dict[str, str]) -> Comment:
    """Convert a CSV row to a ``Comment`` object."""
    return Comment(
        id=row["id"],
        url=row["permalink"],
        body=row["body"],
        subreddit=row["subreddit"],
        created=datetime.strptime(row["date"], "%Y-%m-%d %H:%M:%S %Z").replace(
            tzinfo=timezone.utc
        ),
    )


def iter_comments(archive_path: Path) -> Iterator[Comment]:
    """Yield ``Comment`` objects from a Reddit export ``.zip``.

    Stub — actual parsing lands with the Sprint 1 implementation.
    """
    with zipfile.ZipFile(archive_path) as arch:
        with arch.open("comments.csv") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            for row in reader:
                if row["body"] in ["[removed]", ""]:
                    continue
                yield _row_to_comment(row)
