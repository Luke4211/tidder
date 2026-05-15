"""Output bundle writer/reader.

A ``process`` run produces a single ``.zip`` containing
``flagged_comments.csv``, optionally ``errored_comments.csv``, plus
``buckets.json`` and ``run_metadata.json``. ``remove`` and ``review`` accept
that ``.zip`` directly.

The classifier filters by ``confidence_threshold`` upstream, so every
non-errored ``Classification`` passed in here is, by construction, flagged
for review. The original archive remains the implicit "kept" set — anything
not in ``flagged_comments.csv`` stays on Reddit.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import Classification, RunMetadata, Comment
from .csv_schema import (
    ERRORED_COLUMNS,
    FLAGGED_COLUMNS,
    SAMPLE_COLUMNS,
    format_confidence_mapping,
)

FLAGGED_FILENAME = "flagged_comments.csv"
ERRORED_FILENAME = "errored_comments.csv"
BUCKETS_FILENAME = "buckets.json"
METADATA_FILENAME = "run_metadata.json"


def _flagged_row(c: Classification) -> dict[str, Any]:
    assert c.scores is not None  # non-errored classifications always have scores
    return {
        "id": c.comment.id,
        "url": c.comment.url,
        "confidence_mapping": format_confidence_mapping(c.scores),
        "comment_text": c.comment.body,
        "comment_date": c.comment.created.isoformat(),
        "subreddit": c.comment.subreddit,
        "flagged_for_del": "true",
    }


def _sample_row(c: Comment) -> dict[str, Any]:
    return {
        "id": c.id,
        "permalink": c.url,
        "body": c.body,
        "subreddit": c.subreddit,
        "date": c.created.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def _errored_row(c: Classification) -> dict[str, Any]:
    return {
        "id": c.comment.id,
        "url": c.comment.url,
        "comment_text": c.comment.body,
        "comment_date": c.comment.created.isoformat(),
        "error_message": c.error_message or "",
    }


def _csv_bytes(columns: tuple[str, ...], rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _metadata_json(metadata: RunMetadata) -> bytes:
    data = asdict(metadata)
    for k, v in data.items():
        if isinstance(v, datetime):
            data[k] = v.isoformat()
    return json.dumps(data, indent=2).encode("utf-8")


def _buckets_json(buckets: list[str]) -> bytes:
    mapping = {str(i): b for i, b in enumerate(buckets)}
    return json.dumps(mapping, indent=2).encode("utf-8")


def write_bundle(
    output_dir: Path,
    classifications: list[Classification],
    metadata: RunMetadata,
) -> Path:
    """Write a run's bundle ``.zip`` and return its path.

    The classifier has already filtered by ``confidence_threshold``, so
    successful classifications are unconditionally written to the flagged
    CSV (sorted by ``max_score`` DESC). Errored classifications go to a
    separate CSV, written only if non-empty.
    """
    flagged = sorted(
        (c for c in classifications if not c.errored),
        key=lambda c: c.max_score,
        reverse=True,
    )
    errored = [c for c in classifications if c.errored]

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = metadata.started_at.strftime("%Y%m%d-%H%M%S")
    source_stem = Path(metadata.source_archive).stem
    bundle_path = output_dir / f"{source_stem}_{timestamp}.zip"

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            FLAGGED_FILENAME,
            _csv_bytes(FLAGGED_COLUMNS, [_flagged_row(c) for c in flagged]),
        )
        if errored:
            zf.writestr(
                ERRORED_FILENAME,
                _csv_bytes(ERRORED_COLUMNS, [_errored_row(c) for c in errored]),
            )
        zf.writestr(BUCKETS_FILENAME, _buckets_json(metadata.buckets))
        zf.writestr(METADATA_FILENAME, _metadata_json(metadata))

    return bundle_path


def write_sample(output_dir: Path, comments: list[Comment]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_path = output_dir / "samples.zip"
    with zipfile.ZipFile(sample_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "comments.csv",
            _csv_bytes(SAMPLE_COLUMNS, [_sample_row(c) for c in comments]),
        )
    return sample_path


def read_bundle(bundle_path: Path, extract_to: Path) -> Path:
    """Extract a bundle into ``extract_to`` and return the extracted directory."""
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path) as zf:
        zf.extractall(extract_to)
    return extract_to
