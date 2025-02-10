"""Test suite for pytest-oof CLI commands."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from pytest_oof.__main__ import cli

# Constants from real data
SAMPLE_SUT_ID = "qa-ref-azulprimejdk17"
SAMPLE_SUT_TYPE = "web-service"
SAMPLE_SUT_VERSION = "1.1.0"
SAMPLE_SUT_ENV = "dev"
SAMPLE_TEST_ID = "test_database_connection"

# Mock data
MOCK_SESSION = {
    "session_id": "123",
    "sut_id": SAMPLE_SUT_ID,
    "start_time": "2025-02-09T17:58:48",
    "end_time": "2025-02-09T18:02:00",
    "duration": 192,
    "total_tests": 10,
    "passed_tests": 8,
    "failed_tests": 2,
    "skipped_tests": 0,
    "xfailed_tests": 0,
    "xpassed_tests": 0,
    "warnings": 0,
    "errors": 0,
    "rerun": 0,
    "rerun_outcomes": "[]",
    "sut_type": SAMPLE_SUT_TYPE,
    "sut_version": SAMPLE_SUT_VERSION,
    "sut_env": SAMPLE_SUT_ENV,
}


# Fixtures
@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_db(tmp_path: str) -> Path:
    """Create a temporary database for testing."""
    db_path = Path(tmp_path) / Path("test.db")
    init_db(db_path)  # Initialize the database
    return db_path


@pytest.fixture
def mock_db_client(mocker: MockerFixture):
    """Mock the database client."""
    mock = mocker.patch("pytest_oof.cli.analyze.DBClient", autospec=True)
    mock_instance = mock.return_value
    mock_instance.get_sessions.return_value = [MOCK_SESSION]
    mock_instance.get_test_results.return_value = []
    return mock_instance


@pytest.fixture
def mock_rich_console(mocker: MockerFixture):
    """Mock rich console for console view."""
    mock = mocker.patch("pytest_oof.cli.view.Console", autospec=True)
    mock_instance = mock.return_value
    mock_instance.print = mocker.Mock()
    return mock_instance


# Test oof examples command
@pytest.mark.flaky(reruns=3)
def test_examples_command(runner):
    """Test the examples command."""
    result = runner.invoke(cli, ["examples"])
    assert result.exit_code == 0
    assert "Examples" in result.output


@pytest.mark.flaky(reruns=3)
def test_examples_save_command(runner, tmp_path):
    """Test saving examples to a file."""
    output_file = tmp_path / "examples.md"
    result = runner.invoke(cli, ["examples", "--save", str(output_file)])
    assert result.exit_code == 0
    assert output_file.exists()
    assert output_file.read_text()


# Test oof export results commands
@pytest.mark.flaky(reruns=3)
def test_export_results_no_filters(runner, mock_db_client, temp_db):
    """Test basic export with no filters."""
    result = runner.invoke(cli, ["export", "results", "--db-path", str(temp_db)])
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_export_results_json(runner, mock_db_client, temp_db, tmp_path):
    """Test export to JSON file."""
    output_file = tmp_path / "results.json"
    result = runner.invoke(
        cli,
        ["export", "results", "--db-path", str(temp_db), "--output", str(output_file)],
    )
    assert result.exit_code == 0
    assert output_file.exists()


@pytest.mark.flaky(reruns=3)
def test_export_results_jsonl(runner, mock_db_client, temp_db, tmp_path):
    """Test export to JSONL file."""
    output_file = tmp_path / "results.jsonl"
    result = runner.invoke(
        cli,
        ["export", "results", "--db-path", str(temp_db), "--output", str(output_file)],
    )
    assert result.exit_code == 0
    assert output_file.exists()


@pytest.mark.flaky(reruns=3)
def test_export_results_sut_filters(runner, mock_db_client, temp_db):
    """Test export with SUT filters."""
    result = runner.invoke(
        cli,
        [
            "export",
            "results",
            "--db-path",
            str(temp_db),
            "--sut-id",
            SAMPLE_SUT_ID,
            "--sut-type",
            SAMPLE_SUT_TYPE,
            "--sut-version",
            SAMPLE_SUT_VERSION,
            "--sut-env",
            SAMPLE_SUT_ENV,
        ],
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_export_results_time_filters(runner, mock_db_client, temp_db):
    """Test export with time filters."""
    now = datetime.now()
    start_time = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    result = runner.invoke(
        cli,
        [
            "export",
            "results",
            "--db-path",
            str(temp_db),
            "--start-time",
            start_time,
            "--end-time",
            end_time,
        ],
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_export_results_outcome_filter(runner, mock_db_client, temp_db):
    """Test export with outcome filter."""
    result = runner.invoke(
        cli, ["export", "results", "--db-path", str(temp_db), "--outcome", "failed"]
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_export_results_test_id_filter(runner, mock_db_client, temp_db):
    """Test export with test ID filter."""
    result = runner.invoke(
        cli,
        ["export", "results", "--db-path", str(temp_db), "--test-id", SAMPLE_TEST_ID],
    )
    assert result.exit_code == 0


# Test oof analyze commands
@pytest.mark.flaky(reruns=3)
def test_analyze_failed_command(runner, mock_db_client, temp_db):
    """Test analyze failed command."""
    result = runner.invoke(
        cli, ["analyze", "failed", "--db-path", str(temp_db), "--hours", "24"]
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_analyze_failed_min_failures(runner, mock_db_client, temp_db):
    """Test analyze failed with minimum failures."""
    result = runner.invoke(
        cli, ["analyze", "failed", "--db-path", str(temp_db), "--min-failures", "3"]
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_analyze_failed_sut_filter(runner, mock_db_client, temp_db):
    """Test analyze failed with SUT filter."""
    result = runner.invoke(
        cli, ["analyze", "failed", "--db-path", str(temp_db), "--sut-id", SAMPLE_SUT_ID]
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_analyze_stability_command(runner, mock_db_client, temp_db):
    """Test analyze stability command."""
    result = runner.invoke(
        cli, ["analyze", "stability", "--db-path", str(temp_db), "--days", "7"]
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_analyze_stability_granularity(runner, mock_db_client, temp_db):
    """Test analyze stability with different granularities."""
    for granularity in ["day", "week", "month"]:
        result = runner.invoke(
            cli,
            [
                "analyze",
                "stability",
                "--db-path",
                str(temp_db),
                "--days",
                "30",
                "--granularity",
                granularity,
            ],
        )
        assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_analyze_stability_format(runner, mock_db_client, temp_db):
    """Test analyze stability with different formats."""
    for fmt in ["text", "json"]:
        result = runner.invoke(
            cli,
            [
                "analyze",
                "stability",
                "--db-path",
                str(temp_db),
                "--days",
                "7",
                "--format",
                fmt,
            ],
        )
        assert result.exit_code == 0


# Test database management commands
@pytest.mark.flaky(reruns=3)
def test_list_sessions(runner, mock_db_client, temp_db):
    """Test listing sessions."""
    result = runner.invoke(
        cli, ["analyze", "--db-path", str(temp_db), "--list-sessions"]
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_list_sessions_limit(runner, mock_db_client, temp_db):
    """Test listing sessions with limit."""
    result = runner.invoke(
        cli,
        [
            "analyze",
            "--db-path",
            str(temp_db),
            "--list-sessions",
            "--list-sessions-limit",
            "5",
        ],
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_delete_all_sessions(runner, mock_db_client, temp_db):
    """Test deleting all sessions."""
    result = runner.invoke(cli, ["analyze", "--db-path", str(temp_db), "--delete-all"])
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_delete_last_n_sessions(runner, mock_db_client, temp_db):
    """Test deleting last N sessions."""
    result = runner.invoke(
        cli, ["analyze", "--db-path", str(temp_db), "--delete-last-n", "5"]
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_delete_sessions_time_range(runner, mock_db_client, temp_db):
    """Test deleting sessions in time range."""
    now = datetime.now()
    after_time = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    before_time = now.strftime("%Y-%m-%dT%H:%M:%S")

    result = runner.invoke(
        cli,
        [
            "analyze",
            "--db-path",
            str(temp_db),
            "--delete-after",
            after_time,
            "--delete-before",
            before_time,
        ],
    )
    assert result.exit_code == 0


@pytest.mark.flaky(reruns=3)
def test_delete_sessions_sut(runner, mock_db_client, temp_db):
    """Test deleting sessions for specific SUT."""
    result = runner.invoke(
        cli, ["analyze", "--db-path", str(temp_db), "--delete-sut-id", SAMPLE_SUT_ID]
    )
    assert result.exit_code == 0


# Test view commands
@pytest.mark.flaky(reruns=3)
def test_view_console(runner, mock_db_client, mock_rich_console, temp_db):
    """Test viewing results in console."""
    result = runner.invoke(cli, ["view", "console", "--db-path", str(temp_db)])
    assert result.exit_code == 0


"""
Commands:
  analyze   Analyze test results.
  examples  Show example commands and usage.
  export    Export test results in various formats.
  view      View test results.


oof examples (no output file specified; uses stdout)
oof examples --save examples.md


oof analyze reports stability
    Options:
    --days INTEGER                 Days to analyze
    --sut-id TEXT                  Filter by SUT ID
    --granularity [hour|day|week]
    --format [text|json]
oof analyze reports stability --days 7
oof analyze reports stability --sut-id qa-ref-openjdk17
oof analyze reports stability --granularity hour
oof analyze reports stability --granularity day
oof analyze reports stability --granularity week
oof analyze reports stability --format json
oof analyze reports stability --format text


oof export results --help
Options:
  --output PATH                   Output file path (format determined by
                                  extension: .json or .jsonl)
  --sut-id TEXT                   Filter by SUT ID
  --sut-type TEXT                 Filter by SUT type
  --sut-version TEXT              Filter by SUT version
  --sut-env TEXT                  Filter by SUT environment
  --start-time [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]
                                  Start time for filtering (YYYY-MM-DD
                                  HH:MM:SS)
  --end-time [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]
                                  End time for filtering (YYYY-MM-DD HH:MM:SS)
  --outcome [passed|failed|skipped|xfailed|xpassed]
                                  Filter by test outcome
  --test-id TEXT                  Filter by test ID

oof export results --sut-id qa-ref-openjdk17 (no output file specified; uses stdout)
oof export results --sut-id qa-ref-openjdk17 --output breakpoint_test_results.jsonl
oof export results --sut-type web-service --output breakpoint_test_results.json
oof export results --sut-version 1.0.0 --output breakpoint_test_results.json
oof export results --sut-env qa --output breakpoint_test_results.json
oof export results --start-time 2025-02-08:12:34 --end-time 2025-02-09:00:00
oof export results --outcome failed
oof export results --test-id test_data_validation
"""


def test_examples_save(runner: CliRunner, temp_db: Path):
    """Test saving examples to a file."""
    result = runner.invoke("oof", ["examples", "--save", "examples.md"])
    assert result.exit_code == 0
    assert temp_db.exists()
