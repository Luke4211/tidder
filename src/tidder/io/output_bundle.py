"""Output bundle writer/reader.

A ``process`` run produces a single ``.zip`` containing
``flagged_comments.csv``, optionally ``errored_comments.csv``, plus
``buckets.json`` and ``run_metadata.json``. ``remove`` and ``review`` accept
that ``.zip`` directly.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Classification, RunMetadata

FLAGGED_FILENAME = "flagged_comments.csv"
ERRORED_FILENAME = "errored_comments.csv"
BUCKETS_FILENAME = "buckets.json"
METADATA_FILENAME = "run_metadata.json"


def write_bundle(
    output_dir: Path,
    classifications: list[Classification],
    metadata: RunMetadata,
    confidence_threshold: float,
) -> Path:
    """Write a run's bundle ``.zip`` and return its path. Stub."""
    raise NotImplementedError("output_bundle.write_bundle is not implemented yet.")


def read_bundle(bundle_path: Path, extract_to: Path) -> Path:
    """Extract a bundle to ``extract_to`` and return the extracted dir. Stub."""
    raise NotImplementedError("output_bundle.read_bundle is not implemented yet.")
