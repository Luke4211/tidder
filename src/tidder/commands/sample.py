"""``tidder sample`` — parse comments archive and output a smaller subset."""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Annotated
import typer
from rich.console import Console


from ..archive import random_sample
from ..io.output_bundle import write_sample


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
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory to write the output bundle into. Required argument.",
            file_okay=False,
        ),
    ],
    sample_size: Annotated[
        int,
        typer.Option(
            "--sample-size",
            help="Number of comments to sample from archive. Required argument.",
            min=0,
        ),
    ],
) -> None:
    console = Console()
    samples = random_sample(archive, sample_size)
    write_sample(output_dir, samples)
