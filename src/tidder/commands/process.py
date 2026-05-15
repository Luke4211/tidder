"""``tidder process`` — classify comments and emit a bundle."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ..classifier import run_classification
from ..config import Settings, load_settings
from ..io.output_bundle import write_bundle
from ..llm import get_provider
from ..models import RunMetadata


def run(
    archive: Annotated[
        Path,
        typer.Option(
            "--archive",
            "-a",
            help="Path to the Reddit data-export .zip (typically under uploads/).",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    buckets: Annotated[
        list[str],
        typer.Option(
            "--buckets",
            "-b",
            help="One or more content-type buckets to score each comment against.",
        ),
    ],
    llm_model: Annotated[
        str | None,
        typer.Option("--llm-model", help="LLM model name (required unless in config)."),
    ] = None,
    llm_host: Annotated[
        str | None,
        typer.Option("--llm-host", help="LLM host URL. Default: http://localhost:11434."),
    ] = None,
    llm_provider: Annotated[
        str | None,
        typer.Option("--llm-provider", help="LLM provider key. Default: ollama."),
    ] = None,
    confidence_threshold: Annotated[
        float | None,
        typer.Option(
            "--confidence-threshold",
            "-t",
            help="Min score for a comment to be flagged. Default: 0.75.",
            min=0.0,
            max=1.0,
        ),
    ] = None,
    retry_threshold: Annotated[
        int | None,
        typer.Option(
            "--retry-threshold",
            help="Retries per comment on LLM parse failure. Default: 3.",
            min=0,
        ),
    ] = None,
    concurrency: Annotated[
        int | None,
        typer.Option(
            "--concurrency",
            "-c",
            help="Number of concurrent LLM calls. Default: 4.",
            min=1,
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory to write the output bundle into. Default: outputs/.",
            file_okay=False,
        ),
    ] = None,
) -> None:
    settings = load_settings(
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_host=llm_host,
        confidence_threshold=confidence_threshold,
        retry_threshold=retry_threshold,
        concurrency=concurrency,
        outputs_dir=output_dir,
    )

    if not settings.llm_model:
        raise typer.BadParameter(
            "An LLM model is required (pass --llm-model or set it in config).",
            param_hint="--llm-model",
        )

    asyncio.run(_run_async(archive, buckets, settings))


async def _run_async(
    archive: Path, buckets: list[str], settings: Settings
) -> None:
    console = Console()

    provider = get_provider(
        settings.llm_provider,
        model=settings.llm_model,
        host=settings.llm_host,
    )

    metadata = RunMetadata(
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        source_archive=archive.name,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model or "",
        llm_host=settings.llm_host,
        confidence_threshold=settings.confidence_threshold,
        retry_threshold=settings.retry_threshold,
        concurrency=settings.concurrency,
        buckets=buckets,
    )

    try:
        classifications = await run_classification(
            archive,
            buckets,
            provider,
            concurrency=settings.concurrency,
            confidence_threshold=settings.confidence_threshold,
            retry_threshold=settings.retry_threshold,
        )
    finally:
        await provider.aclose()

    metadata.finished_at = datetime.now(timezone.utc)
    bundle_path = write_bundle(settings.outputs_dir, classifications, metadata)

    flagged_count = sum(1 for c in classifications if not c.errored)
    errored_count = sum(1 for c in classifications if c.errored)

    console.print()
    console.print(f"[bold green]✓[/] Wrote bundle to [cyan]{bundle_path}[/]")
    console.print(f"  [green]flagged: {flagged_count}[/]  [red]errored: {errored_count}[/]")
    console.print()
    console.print("Next: review the bundle, then run:")
    console.print(f"  [bold]tidder remove --input {bundle_path}[/]")
