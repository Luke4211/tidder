"""``tidder process`` — classify comments and emit a bundle."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from ..config import load_settings


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


async def _run_async(archive: Path, buckets: list[str], settings) -> None:
    raise NotImplementedError("process.run is not implemented yet.")
