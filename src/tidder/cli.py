"""Top-level typer app. Subcommand bodies live under ``tidder.commands``."""

from __future__ import annotations

import typer

from . import __version__
from .commands import process as process_cmd
from .commands import remove as remove_cmd

app = typer.Typer(
    name="tidder",
    help="LLM-driven cleanup tool for Reddit comment history.",
    no_args_is_help=True,
    add_completion=False,
)

app.command("process", help="Classify comments and emit a flagged-comments bundle.")(
    process_cmd.run
)
app.command("remove", help="Overwrite or delete flagged comments via the Reddit API.")(
    remove_cmd.run
)


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", help="Print the tidder version and exit."
    ),
) -> None:
    if version:
        typer.echo(f"tidder {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
