"""``tidder remove`` — overwrite or delete flagged comments."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from ..config import load_settings


class Mode(StrEnum):
    overwrite = "overwrite"
    delete = "delete"


class OverwriteStyle(StrEnum):
    random = "random"
    llm = "llm"
    fixed = "fixed"


def run(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to the output bundle .zip produced by `tidder process`.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    mode: Annotated[
        Mode,
        typer.Option(
            "--mode",
            help="Whether to overwrite comment bodies or delete them.",
            case_sensitive=False,
        ),
    ] = Mode.overwrite,
    overwrite_style: Annotated[
        OverwriteStyle,
        typer.Option(
            "--overwrite-style",
            help="How to generate replacement bodies (only used with --mode overwrite).",
            case_sensitive=False,
        ),
    ] = OverwriteStyle.random,
    overwrite_text: Annotated[
        str | None,
        typer.Option(
            "--overwrite-text",
            help="Fixed replacement text (only valid with --overwrite-style fixed).",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Report what would happen without making any Reddit API calls.",
        ),
    ] = False,
    llm_model: Annotated[
        str | None,
        typer.Option("--llm-model", help="LLM model (required with --overwrite-style llm)."),
    ] = None,
    llm_host: Annotated[
        str | None,
        typer.Option("--llm-host", help="LLM host URL."),
    ] = None,
    llm_provider: Annotated[
        str | None,
        typer.Option("--llm-provider", help="LLM provider key."),
    ] = None,
    concurrency: Annotated[
        int | None,
        typer.Option(
            "--concurrency",
            "-c",
            help="Concurrent Reddit API calls (bounded by rate limits).",
            min=1,
        ),
    ] = None,
) -> None:
    if overwrite_style == OverwriteStyle.fixed and not overwrite_text:
        raise typer.BadParameter(
            "--overwrite-style fixed requires --overwrite-text.",
            param_hint="--overwrite-text",
        )
    if overwrite_text and overwrite_style != OverwriteStyle.fixed:
        raise typer.BadParameter(
            "--overwrite-text is only valid with --overwrite-style fixed.",
            param_hint="--overwrite-text",
        )

    settings = load_settings(
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_host=llm_host,
        concurrency=concurrency,
    )

    if (
        mode == Mode.overwrite
        and overwrite_style == OverwriteStyle.llm
        and not settings.llm_model
    ):
        raise typer.BadParameter(
            "--overwrite-style llm requires --llm-model (or a configured default).",
            param_hint="--llm-model",
        )

    asyncio.run(
        _run_async(
            input_path=input,
            mode=mode,
            overwrite_style=overwrite_style,
            overwrite_text=overwrite_text,
            dry_run=dry_run,
            settings=settings,
        )
    )


async def _run_async(**_: object) -> None:
    raise NotImplementedError("remove.run is not implemented yet.")
