"""Smoke tests: the package imports and the CLI wires up."""

from __future__ import annotations

from typer.testing import CliRunner

from tidder.cli import app


def test_help_runs():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "tidder" in result.stdout
    assert "process" in result.stdout
    assert "remove" in result.stdout


def test_process_help_runs():
    result = CliRunner().invoke(app, ["process", "--help"])
    assert result.exit_code == 0
    assert "--archive" in result.stdout
    assert "--buckets" in result.stdout


def test_remove_help_runs():
    result = CliRunner().invoke(app, ["remove", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.stdout
    assert "--dry-run" in result.stdout
