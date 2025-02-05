"""Tests for analyze_results.py CLI."""
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from pytest_oof.analyze_results import main
from pytest_oof.db import init_db


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database file."""
    db_path = tmp_path / "test.db"
    init_db(db_path)  # Initialize the database
    return db_path


def test_help(runner):
    """Test that --help works."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Analyze and manage test results" in result.output


def test_analyze_empty_db(runner, temp_db):
    """Test analyzing an empty database."""
    result = runner.invoke(main, [str(temp_db)])
    assert result.exit_code == 0
    assert "Total Sessions: 0" in result.output


def test_delete_all(runner, temp_db):
    """Test --delete-all flag."""
    result = runner.invoke(main, [str(temp_db), "--delete-all", "--no-analyze"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_delete_last_n(runner, temp_db):
    """Test --delete-last flag."""
    result = runner.invoke(main, [str(temp_db), "--delete-last", "5", "--no-analyze"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_delete_time_window(runner, temp_db):
    """Test time-based deletion."""
    result = runner.invoke(
        main,
        [
            str(temp_db),
            "--delete-after",
            "2025-01-01T00:00:00",
            "--delete-before",
            "2025-02-01T00:00:00",
            "--no-analyze",
        ],
    )
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_delete_sut(runner, temp_db):
    """Test SUT-based deletion."""
    result = runner.invoke(
        main,
        [str(temp_db), "--delete-sut-id", "test-app", "--no-analyze"],
    )
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_invalid_timestamp(runner, temp_db):
    """Test handling of invalid timestamp format."""
    result = runner.invoke(
        main,
        [str(temp_db), "--delete-after", "invalid-date"],
    )
    assert result.exit_code != 0
    assert "Timestamp must be in ISO format" in result.output


def test_analyze_with_filters(runner, temp_db):
    """Test analysis with various filters."""
    result = runner.invoke(
        main,
        [
            str(temp_db),
            "--sut-id", "test-app",
            "--sut-type", "web",
            "--after", "2025-01-01T00:00:00",
            "--before", "2025-02-01T00:00:00",
            "--last", "5",
            "--outcome", "failed",
        ],
    )
    assert result.exit_code == 0
    assert "Summary Statistics" in result.output


def test_export_json(runner, temp_db, tmp_path):
    """Test exporting results to JSON."""
    export_file = tmp_path / "results.json"
    result = runner.invoke(
        main,
        [str(temp_db), "--export", str(export_file)],
    )
    assert result.exit_code == 0


def test_export_jsonl(runner, temp_db, tmp_path):
    """Test exporting results to JSONL."""
    export_file = tmp_path / "results.jsonl"
    result = runner.invoke(
        main,
        [str(temp_db), "--export", str(export_file)],
    )
    assert result.exit_code == 0


def test_delete_and_analyze(runner, temp_db):
    """Test deleting and analyzing in one command."""
    result = runner.invoke(
        main,
        [str(temp_db), "--delete-last", "5", "--analyze"],
    )
    assert result.exit_code == 0
    assert "Deleted" in result.output
    assert "Summary Statistics" in result.output
