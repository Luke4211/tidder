"""Tests for the output bundle writer/reader."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tidder.io.csv_schema import ERRORED_COLUMNS, FLAGGED_COLUMNS
from tidder.io.output_bundle import (
    BUCKETS_FILENAME,
    ERRORED_FILENAME,
    FLAGGED_FILENAME,
    METADATA_FILENAME,
    read_bundle,
    write_bundle,
)
from tidder.models import Classification, Comment, RunMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _comment(id: str, subreddit: str = "python", body: str = "hello") -> Comment:
    return Comment(
        id=id,
        url=f"https://reddit.com/r/{subreddit}/comments/{id}",
        body=body,
        subreddit=subreddit,
        created=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


def _classification(
    id: str,
    scores: dict[int, float] | None = None,
    *,
    errored: bool = False,
    error_message: str | None = None,
    subreddit: str = "python",
    body: str = "hello",
) -> Classification:
    return Classification(
        comment=_comment(id, subreddit=subreddit, body=body),
        scores=scores,
        errored=errored,
        error_message=error_message,
    )


def _metadata(buckets: list[str] | None = None, source: str = "export.zip") -> RunMetadata:
    return RunMetadata(
        started_at=datetime(2025, 6, 15, 9, 30, 45, tzinfo=timezone.utc),
        finished_at=datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        source_archive=source,
        llm_provider="ollama",
        llm_model="llama3.1:8b",
        llm_host="http://localhost:11434",
        confidence_threshold=0.75,
        retry_threshold=3,
        concurrency=4,
        buckets=buckets or ["pii", "politics"],
    )


def _read_csv_from_zip(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with zf.open(name) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
        return list(reader)


# ---------------------------------------------------------------------------
# write_bundle
# ---------------------------------------------------------------------------


def test_write_bundle_creates_zip_with_expected_files(tmp_path: Path):
    classifications = [_classification("c1", {0: 0.9, 1: 0.1})]
    bundle = write_bundle(tmp_path, classifications, _metadata())

    assert bundle.exists()
    assert bundle.suffix == ".zip"

    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
    assert FLAGGED_FILENAME in names
    assert BUCKETS_FILENAME in names
    assert METADATA_FILENAME in names


def test_write_bundle_filename_uses_source_stem_and_timestamp(tmp_path: Path):
    bundle = write_bundle(
        tmp_path, [_classification("c1", {0: 0.9})], _metadata(source="my_export.zip")
    )
    # started_at is 2025-06-15 09:30:45 UTC.
    assert bundle.name == "my_export_20250615-093045.zip"


def test_write_bundle_omits_errored_csv_when_empty(tmp_path: Path):
    bundle = write_bundle(tmp_path, [_classification("c1", {0: 0.9})], _metadata())
    with zipfile.ZipFile(bundle) as zf:
        assert ERRORED_FILENAME not in zf.namelist()


def test_write_bundle_includes_errored_csv_when_present(tmp_path: Path):
    classifications = [
        _classification("c1", {0: 0.9}),
        _classification("e1", errored=True, error_message="parse failure"),
    ]
    bundle = write_bundle(tmp_path, classifications, _metadata())

    with zipfile.ZipFile(bundle) as zf:
        assert ERRORED_FILENAME in zf.namelist()
        errored_rows = _read_csv_from_zip(zf, ERRORED_FILENAME)

    assert len(errored_rows) == 1
    assert errored_rows[0]["id"] == "e1"
    assert errored_rows[0]["error_message"] == "parse failure"


def test_write_bundle_flagged_sorted_by_max_score_desc(tmp_path: Path):
    classifications = [
        _classification("low", {0: 0.80, 1: 0.10}),
        _classification("high", {0: 0.95, 1: 0.05}),
        _classification("mid", {0: 0.85, 1: 0.20}),
    ]
    bundle = write_bundle(tmp_path, classifications, _metadata())

    with zipfile.ZipFile(bundle) as zf:
        rows = _read_csv_from_zip(zf, FLAGGED_FILENAME)

    assert [r["id"] for r in rows] == ["high", "mid", "low"]


def test_write_bundle_flagged_row_shape(tmp_path: Path):
    c = _classification("c1", {0: 0.92, 1: 0.04}, subreddit="askreddit", body="hi")
    bundle = write_bundle(tmp_path, [c], _metadata())

    with zipfile.ZipFile(bundle) as zf:
        rows = _read_csv_from_zip(zf, FLAGGED_FILENAME)

    assert list(rows[0].keys()) == list(FLAGGED_COLUMNS)
    row = rows[0]
    assert row["id"] == "c1"
    assert row["url"] == "https://reddit.com/r/askreddit/comments/c1"
    assert row["confidence_mapping"] == "0:0.92,1:0.04"
    assert row["comment_text"] == "hi"
    assert row["subreddit"] == "askreddit"
    assert row["flagged_for_del"] == "true"
    # ISO format for the date column.
    assert "T" in row["comment_date"]


def test_write_bundle_errored_row_shape(tmp_path: Path):
    c = _classification("e1", errored=True, error_message="oops")
    bundle = write_bundle(tmp_path, [c], _metadata())

    with zipfile.ZipFile(bundle) as zf:
        rows = _read_csv_from_zip(zf, ERRORED_FILENAME)

    assert list(rows[0].keys()) == list(ERRORED_COLUMNS)


def test_write_bundle_buckets_json(tmp_path: Path):
    bundle = write_bundle(
        tmp_path,
        [_classification("c1", {0: 0.9})],
        _metadata(buckets=["pii", "drugs", "politics"]),
    )
    with zipfile.ZipFile(bundle) as zf:
        data = json.loads(zf.read(BUCKETS_FILENAME))

    assert data == {"0": "pii", "1": "drugs", "2": "politics"}


def test_write_bundle_metadata_json(tmp_path: Path):
    meta = _metadata()
    bundle = write_bundle(
        tmp_path, [_classification("c1", {0: 0.9})], meta
    )
    with zipfile.ZipFile(bundle) as zf:
        data = json.loads(zf.read(METADATA_FILENAME))

    assert data["llm_model"] == "llama3.1:8b"
    assert data["confidence_threshold"] == 0.75
    assert data["concurrency"] == 4
    assert data["buckets"] == ["pii", "politics"]
    # Datetime fields serialized as ISO strings.
    assert data["started_at"].startswith("2025-06-15T09:30:45")
    assert data["finished_at"].startswith("2025-06-15T10:00:00")


def test_write_bundle_creates_output_dir_if_missing(tmp_path: Path):
    nested = tmp_path / "deeply" / "nested" / "outputs"
    bundle = write_bundle(
        nested, [_classification("c1", {0: 0.9})], _metadata()
    )
    assert bundle.parent == nested
    assert nested.is_dir()


def test_write_bundle_empty_classifications(tmp_path: Path):
    bundle = write_bundle(tmp_path, [], _metadata())
    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
        # Header-only flagged CSV is still written.
        flagged_rows = _read_csv_from_zip(zf, FLAGGED_FILENAME)

    assert FLAGGED_FILENAME in names
    assert ERRORED_FILENAME not in names
    assert flagged_rows == []


def test_write_bundle_errored_only(tmp_path: Path):
    """All classifications failed — flagged CSV empty (header only), errored populated."""
    classifications = [
        _classification("e1", errored=True, error_message="x"),
        _classification("e2", errored=True, error_message="y"),
    ]
    bundle = write_bundle(tmp_path, classifications, _metadata())

    with zipfile.ZipFile(bundle) as zf:
        flagged = _read_csv_from_zip(zf, FLAGGED_FILENAME)
        errored = _read_csv_from_zip(zf, ERRORED_FILENAME)

    assert flagged == []
    assert len(errored) == 2


# ---------------------------------------------------------------------------
# read_bundle
# ---------------------------------------------------------------------------


def test_read_bundle_extracts_all_files(tmp_path: Path):
    bundle = write_bundle(
        tmp_path,
        [
            _classification("c1", {0: 0.9}),
            _classification("e1", errored=True, error_message="x"),
        ],
        _metadata(),
    )
    extract_to = tmp_path / "extracted"
    result = read_bundle(bundle, extract_to)

    assert result == extract_to
    assert (extract_to / FLAGGED_FILENAME).is_file()
    assert (extract_to / ERRORED_FILENAME).is_file()
    assert (extract_to / BUCKETS_FILENAME).is_file()
    assert (extract_to / METADATA_FILENAME).is_file()


def test_read_bundle_creates_target_dir(tmp_path: Path):
    bundle = write_bundle(
        tmp_path, [_classification("c1", {0: 0.9})], _metadata()
    )
    extract_to = tmp_path / "does" / "not" / "exist"
    read_bundle(bundle, extract_to)
    assert extract_to.is_dir()


def test_round_trip_preserves_content(tmp_path: Path):
    classifications = [
        _classification("a", {0: 0.91, 1: 0.05}, subreddit="aww"),
        _classification("b", {0: 0.80, 1: 0.20}, subreddit="python"),
    ]
    bundle = write_bundle(tmp_path, classifications, _metadata())

    extract_to = tmp_path / "out"
    read_bundle(bundle, extract_to)

    with (extract_to / FLAGGED_FILENAME).open(newline="") as f:
        rows = list(csv.DictReader(f))

    assert [r["id"] for r in rows] == ["a", "b"]
    assert rows[0]["subreddit"] == "aww"
    assert rows[1]["confidence_mapping"] == "0:0.80,1:0.20"
