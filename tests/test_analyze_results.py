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
    result = runner.invoke(main, [str(temp_db), "--delete-all"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_delete_last_n(runner, temp_db):
    """Test --delete-last flag."""
    result = runner.invoke(main, [str(temp_db), "--delete-last", "5"])
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
        ],
    )
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_delete_sut(runner, temp_db):
    """Test SUT-based deletion."""
    result = runner.invoke(
        main,
        [str(temp_db), "--delete-sut-id", "test-app"],
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
            "--sut-id",
            "test-app",
            "--sut-type",
            "web",
            "--after",
            "2025-01-01T00:00:00",
            "--before",
            "2025-02-01T00:00:00",
            "--last",
            "5",
            "--outcome",
            "failed",
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


"""Test suite for analyze_results CLI."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from pytest_oof.analyze_results import analyze_results, main
from pytest_oof.db import init_db

# Test data
MOCK_SESSIONS = [
    {
        "id": 1,
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "start_time": "2025-02-05 08:56:08",
        "end_time": "2025-02-05 08:56:12",
        "duration": 4.6,
        "sut_id": "my-app",
        "sut_type": "prod",
        "sut_version": "1.0.0",
    },
    {
        "id": 2,
        "session_id": "550e8400-e29b-41d4-a716-446655440001",
        "start_time": "2025-02-05 08:55:00",
        "end_time": "2025-02-05 08:55:03",
        "duration": 3.2,
        "sut_id": "my-app",
        "sut_type": "dev",
        "sut_version": "1.0.1",
    },
]

MOCK_TEST_RESULTS = [
    {
        "test_id": "test_one",
        "outcome": "PASSED",
        "duration": 1.2,
    },
    {
        "test_id": "test_two",
        "outcome": "FAILED",
        "duration": 0.8,
        "error_message": "assertion failed",
    },
]


@pytest.fixture
def mock_db(tmp_path: Path) -> Path:
    """Create a mock database file."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def mock_db_with_data(mock_db: Path, mocker: MockerFixture) -> Path:
    """Create a mock database with test data."""
    mocker.patch(
        "pytest_oof.analyze_results.list_recent_sessions", return_value=MOCK_SESSIONS
    )
    mocker.patch(
        "pytest_oof.analyze_results.export_results",
        return_value=[
            {"session": {**MOCK_SESSIONS[0], "test_results": MOCK_TEST_RESULTS}}
        ],
    )
    return mock_db


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


def test_list_sessions(runner: CliRunner, mock_db_with_data: Path) -> None:
    """Test --list-sessions option."""
    result = runner.invoke(main, [str(mock_db_with_data), "--list-sessions"])
    assert result.exit_code == 0
    assert "Recent Test Sessions:" in result.output
    assert "my-app (prod)" in result.output
    assert "my-app (dev)" in result.output
    assert "550e8400" in result.output  # Short session ID


def test_list_sessions_empty(
    runner: CliRunner, mock_db: Path, mocker: MockerFixture
) -> None:
    """Test --list-sessions with no sessions."""
    mocker.patch("pytest_oof.analyze_results.list_recent_sessions", return_value=[])
    result = runner.invoke(main, [str(mock_db), "--list-sessions"])
    assert result.exit_code == 0
    assert "No test sessions found" in result.output


def test_show_session_by_id(
    runner: CliRunner, mock_db_with_data: Path, mocker: MockerFixture
) -> None:
    """Test --id option with full session ID."""
    session_id = "550e8400-e29b-41d4-a716-446655440000"

    # Create mock cursor for database queries
    mock_cursor = mocker.MagicMock()

    # Mock cursor.execute to handle different queries
    def mock_execute(query, params):
        if "WHERE session_id = ?" in query:
            mock_cursor.fetchone.return_value = (1,)  # Return ID 1
        return mock_cursor

    mock_cursor.execute = mock_execute

    # Create mock connection
    mock_conn = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    # Patch database connection
    mocker.patch("pytest_oof.analyze_results.db_connection", return_value=mock_conn)

    # Mock export_results to return session with all required fields
    mocker.patch(
        "pytest_oof.analyze_results.export_results",
        return_value=[
            {
                "session": {
                    "session_id": session_id,
                    "start_time": "2023-01-01T00:00:00",
                    "end_time": "2023-01-01T00:01:00",
                    "duration": 60,
                    "sut_id": "test-sut",
                    "sut_type": "test",
                    "sut_version": "1.0.0",
                    "sut_env": "prod",
                },
                "test_results": MOCK_TEST_RESULTS,
            }
        ],
    )

    result = runner.invoke(main, [str(mock_db_with_data), "--id", session_id])
    assert result.exit_code == 0
    assert session_id in result.output


def test_show_session_by_short_id(
    runner: CliRunner, mock_db_with_data: Path, mocker: MockerFixture
) -> None:
    """Test --id option with short session ID."""
    full_id = "550e8400-e29b-41d4-a716-446655440000"

    # Create mock cursor for database queries
    mock_cursor = mocker.MagicMock()

    # Mock cursor.execute to handle different queries
    def mock_execute(query, params):
        if "WHERE session_id = ?" in query:
            mock_cursor.fetchone.return_value = None if params[0] != full_id else (1,)
        elif "WHERE session_id LIKE ?" in query:
            mock_cursor.fetchall.return_value = [(full_id,)]
        return mock_cursor

    mock_cursor.execute = mock_execute

    # Create mock connection
    mock_conn = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    # Patch database connection
    mocker.patch("pytest_oof.analyze_results.db_connection", return_value=mock_conn)

    # Mock export_results to return session with all required fields
    mocker.patch(
        "pytest_oof.analyze_results.export_results",
        return_value=[
            {
                "session": {
                    "session_id": full_id,
                    "start_time": "2023-01-01T00:00:00",
                    "end_time": "2023-01-01T00:01:00",
                    "duration": 60,
                    "sut_id": "test-sut",
                    "sut_type": "test",
                    "sut_version": "1.0.0",
                    "sut_env": "prod",
                },
                "test_results": MOCK_TEST_RESULTS,
            }
        ],
    )

    result = runner.invoke(main, [str(mock_db_with_data), "--id", "440000"])
    assert result.exit_code == 0
    assert full_id in result.output


def test_show_session_not_found(
    runner: CliRunner, mock_db: Path, mocker: MockerFixture
) -> None:
    """Test --id with non-existent session ID."""
    session_id = "nonexistent"

    # Create mock cursor for database queries
    mock_cursor = mocker.MagicMock()

    # Mock cursor.execute to handle different queries
    def mock_execute(query, params):
        if "WHERE session_id = ?" in query:
            mock_cursor.fetchone.return_value = None
        elif "WHERE session_id LIKE ?" in query:
            mock_cursor.fetchall.return_value = []
        return mock_cursor

    mock_cursor.execute = mock_execute

    # Create mock connection
    mock_conn = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    # Patch database connection
    mocker.patch("pytest_oof.analyze_results.db_connection", return_value=mock_conn)

    result = runner.invoke(main, [str(mock_db), "--id", session_id])
    assert result.exit_code == 0
    assert f"No session found with session ID {session_id}" in result.output


def test_show_session_multiple_matches(
    runner: CliRunner, mock_db: Path, mocker: MockerFixture
) -> None:
    """Test --id with ambiguous session ID."""
    # Create mock cursor for database queries
    mock_cursor = mocker.MagicMock()

    # Mock cursor.execute to handle different queries
    def mock_execute(query, params):
        if "WHERE session_id = ?" in query:
            # For exact match query, return no results
            mock_cursor.fetchone.return_value = None
        elif "WHERE session_id LIKE ?" in query:
            # Second query with LIKE returns multiple matches
            mock_cursor.fetchall.return_value = [
                ("550e8400-e29b-41d4-a716-446655440000",),
                ("550e8400-e29b-41d4-a716-446655440001",),
            ]
        return mock_cursor

    mock_cursor.execute = mock_execute

    # Create mock connection that returns our cursor
    mock_conn = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = None

    # Patch the database connection
    mocker.patch("pytest_oof.analyze_results.db_connection", return_value=mock_conn)

    # Run the test
    result = runner.invoke(main, [str(mock_db), "--id", "440"])
    assert result.exit_code == 0
    assert "Multiple sessions found" in result.output


def test_filter_by_sut(runner: CliRunner, mock_db_with_data: Path) -> None:
    """Test SUT filtering options."""
    result = runner.invoke(
        main, [str(mock_db_with_data), "--sut-id", "my-app", "--sut-type", "prod"]
    )
    assert result.exit_code == 0
    assert "Summary Statistics:" in result.output


def test_filter_by_date(runner: CliRunner, mock_db_with_data: Path) -> None:
    """Test date filtering options."""
    result = runner.invoke(
        main,
        [
            str(mock_db_with_data),
            "--after",
            "2025-02-01T00:00:00Z",
            "--before",
            "2025-02-06T00:00:00Z",
        ],
    )
    assert result.exit_code == 0
    assert "Summary Statistics:" in result.output


def test_filter_by_outcome(runner: CliRunner, mock_db_with_data: Path) -> None:
    """Test outcome filtering."""
    result = runner.invoke(main, [str(mock_db_with_data), "--outcome", "failed"])
    assert result.exit_code == 0
    assert "Summary Statistics:" in result.output


def test_export_results(
    runner: CliRunner, mock_db_with_data: Path, tmp_path: Path
) -> None:
    """Test exporting results to file."""
    export_file = tmp_path / "export.json"
    result = runner.invoke(main, [str(mock_db_with_data), "--export", str(export_file)])
    assert result.exit_code == 0


def test_delete_all(runner: CliRunner, mock_db: Path, mocker: MockerFixture) -> None:
    """Test --delete-all option."""
    mock_delete = mocker.patch(
        "pytest_oof.analyze_results.delete_results", return_value=2
    )
    result = runner.invoke(main, [str(mock_db), "--delete-all"])
    assert result.exit_code == 0
    assert "Deleted 2 test sessions" in result.output
    mock_delete.assert_called_once()


def test_delete_with_filters(
    runner: CliRunner, mock_db: Path, mocker: MockerFixture
) -> None:
    """Test delete with filters."""
    mock_delete = mocker.patch(
        "pytest_oof.analyze_results.delete_results", return_value=1
    )
    result = runner.invoke(
        main,
        [
            str(mock_db),
            "--delete-before",
            "2025-02-01T00:00:00Z",
            "--delete-sut-id",
            "my-app",
        ],
    )
    assert result.exit_code == 0
    assert "Deleted 1 test sessions" in result.output
    mock_delete.assert_called_once()


def test_invalid_db_path(runner: CliRunner, tmp_path: Path) -> None:
    """Test with non-existent database file."""
    bad_path = tmp_path / "nonexistent.db"
    result = runner.invoke(main, [str(bad_path)])
    assert result.exit_code == 2  # Click's error exit code
    assert "does not exist" in result.output


def test_delete_and_analyze(runner, temp_db):
    """Test deleting and analyzing in one command."""
    result = runner.invoke(
        main,
        [str(temp_db), "--delete-last", "5"],
    )
    assert result.exit_code == 0
    assert "Deleted" in result.output
