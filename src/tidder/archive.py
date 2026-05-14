"""Reddit data-export archive parsing.

Reddit's data-export ``.zip`` contains many CSVs; for tidder we care about
``comments.csv`` (and ``comment_headers.csv`` when present, which carries
column names some older exports omit).
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from .models import Comment

# Column index of the comment body in a headerless comments.csv row.
_BODY_COL = 10

_SKIP_BODIES = frozenset({"[removed]", ""})


def _find_member(zf: zipfile.ZipFile, name: str) -> str:
    """Locate a zip member case-insensitively, handling optional subdirectories."""
    lower = name.lower()
    for member in zf.namelist():
        if member.lower() == lower or member.lower().endswith("/" + lower):
            return member
    raise FileNotFoundError(f"{name!r} not found in archive")


def _row_to_comment(row: dict[str, str]) -> Comment:
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
    """Yield ``Comment`` objects from a Reddit export ``.zip``, skipping removed/empty bodies."""
    with zipfile.ZipFile(archive_path) as zf:
        member = _find_member(zf, "comments.csv")
        with zf.open(member) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            for row in reader:
                if row["body"] in _SKIP_BODIES:
                    continue
                yield _row_to_comment(row)


def count_comments(archive_path: Path) -> int:
    """Return the number of classifiable comments in the archive.

    Fast pre-pass used to set the progress bar total before classification
    begins. Applies the same skip logic as ``iter_comments`` so the count
    matches what the pipeline will actually process.
    """
    with zipfile.ZipFile(archive_path) as zf:
        member = _find_member(zf, "comments.csv")
        with zf.open(member) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            next(reader)  # skip header row
            return sum(1 for row in reader if row[_BODY_COL] not in _SKIP_BODIES)
