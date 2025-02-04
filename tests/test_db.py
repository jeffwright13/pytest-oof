"""Tests for database functionality."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from pytest_mock import MockerFixture

from pytest_oof.db import (
    add_console_line,
    add_report_metric,
    add_session,
    add_test_result,
    export_results,
    init_db,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for testing."""
    db_file = tmp_path / "test.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def mock_datetime(mocker: MockerFixture):
    """Mock datetime to return a fixed time."""
    mock_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock = mocker.patch("pytest_oof.db.datetime")
    mock.now.return_value = mock_now
    mock.side_effect = datetime
    return mock_now


def test_add_session(db_path, mock_datetime):
    """Test adding a test session."""
    session_id = add_session(
        db_path,
        start_time=mock_datetime,
        sut_id="test-sut",
        sut_type="unit-test",
        sut_version="1.0.0",
        sut_env="test",
    )

    # Query and verify
    results = export_results(db_path, session_id=session_id)
    assert len(results) == 1
    session = results[0]["session"]
    assert session["sut_id"] == "test-sut"
    assert session["sut_type"] == "unit-test"
    assert session["sut_version"] == "1.0.0"
    assert session["sut_env"] == "test"
    assert session["start_time"] == "2025-01-01 12:00:00+00:00"


def test_add_test_results(db_path, mock_datetime):
    """Test adding test results."""
    # Create session
    session_id = add_session(db_path, mock_datetime)

    # Add some test results
    add_test_result(
        db_path,
        session_id=session_id,
        test_id="test_one",
        outcome="passed",
        timestamp=mock_datetime,
        duration=1.23,
    )
    add_test_result(
        db_path,
        session_id=session_id,
        test_id="test_two",
        outcome="failed",
        timestamp=mock_datetime,
        duration=0.45,
        error_message="assertion error",
        error_type="AssertionError",
        error_traceback="test_file.py:123",
    )

    # Query and verify
    results = export_results(db_path, session_id=session_id)
    assert len(results) == 1
    test_results = results[0]["test_results"]
    assert len(test_results) == 2

    passed_test = next(t for t in test_results if t["test_id"] == "test_one")
    assert passed_test["outcome"] == "passed"
    assert passed_test["duration"] == 1.23
    assert passed_test["timestamp"] == "2025-01-01 12:00:00+00:00"

    failed_test = next(t for t in test_results if t["test_id"] == "test_two")
    assert failed_test["outcome"] == "failed"
    assert failed_test["duration"] == 0.45
    assert failed_test["error_type"] == "AssertionError"
    assert failed_test["error_message"] == "assertion error"
    assert failed_test["error_traceback"] == "test_file.py:123"
    assert failed_test["timestamp"] == "2025-01-01 12:00:00+00:00"


def test_export_results_filtering(db_path, mock_datetime):
    """Test filtering capabilities of export_results."""
    # Create two sessions with different SUTs
    session1 = add_session(
        db_path,
        start_time=mock_datetime,
        sut_id="sut1",
        sut_version="1.0",
    )
    session2 = add_session(
        db_path,
        start_time=mock_datetime,
        sut_id="sut2",
        sut_version="2.0",
    )

    # Add test results to both sessions
    add_test_result(db_path, session1, "test1", "passed", mock_datetime)
    add_test_result(db_path, session2, "test1", "failed", mock_datetime)

    # Test filtering by SUT
    results = export_results(db_path, sut_id="sut1")
    assert len(results) == 1
    assert results[0]["session"]["sut_id"] == "sut1"
    assert results[0]["test_results"][0]["outcome"] == "passed"

    # Test filtering by outcome
    results = export_results(db_path, outcome="failed")
    assert len(results) == 1
    assert results[0]["session"]["sut_id"] == "sut2"

    # Test filtering by test_id
    results = export_results(db_path, test_id="test1")
    assert len(results) == 2  # Should find test1 in both sessions


def test_export_results_to_file(db_path, mock_datetime, tmp_path):
    """Test exporting results to a JSON file."""
    # Create session and add results
    session_id = add_session(db_path, mock_datetime)
    add_test_result(
        db_path,
        session_id,
        "test1",
        "passed",
        mock_datetime,
    )

    # Export to file
    output_file = tmp_path / "results.json"
    export_results(db_path, output_file=output_file)

    # Read and verify JSON
    with open(output_file) as f:
        data = json.load(f)

    assert len(data) == 1
    assert len(data[0]["test_results"]) == 1
    assert data[0]["test_results"][0]["test_id"] == "test1"
    assert data[0]["test_results"][0]["timestamp"] == "2025-01-01 12:00:00+00:00"


def test_time_based_filtering(db_path, mock_datetime):
    """Test filtering results by time range."""
    # Create sessions at different times
    time1 = mock_datetime
    time2 = mock_datetime + timedelta(hours=1)
    time3 = mock_datetime + timedelta(hours=2)

    session1 = add_session(db_path, time1, sut_id="sut1")
    session2 = add_session(db_path, time2, sut_id="sut2")
    session3 = add_session(db_path, time3, sut_id="sut3")

    # Add test results
    add_test_result(db_path, session1, "test1", "passed", time1)
    add_test_result(db_path, session2, "test2", "passed", time2)
    add_test_result(db_path, session3, "test3", "passed", time3)

    # Test start_time filter
    results = export_results(db_path, start_time=time2)
    assert len(results) == 2
    sut_ids = {r["session"]["sut_id"] for r in results}
    assert sut_ids == {"sut2", "sut3"}

    # Test end_time filter
    results = export_results(db_path, end_time=time2)
    assert len(results) == 2
    sut_ids = {r["session"]["sut_id"] for r in results}
    assert sut_ids == {"sut1", "sut2"}

    # Test time range
    results = export_results(
        db_path,
        start_time=time1 + timedelta(minutes=30),
        end_time=time2 + timedelta(minutes=30),
    )
    assert len(results) == 1
    assert results[0]["session"]["sut_id"] == "sut2"


def test_metrics_and_console_output(db_path, mock_datetime):
    """Test storing and retrieving metrics and console output."""
    session_id = add_session(db_path, mock_datetime)

    # Add console output
    add_console_line(
        db_path, session_id, mock_datetime, 1, "collecting tests...", line_type="header"
    )
    add_console_line(
        db_path,
        session_id,
        mock_datetime,
        2,
        "test_example.py::test_one PASSED",
        line_type="test_result",
        parsed_data=json.dumps({"test_id": "test_one", "outcome": "passed"}),
    )

    # Add metrics
    add_report_metric(db_path, session_id, "collected", 10, mock_datetime)
    add_report_metric(db_path, session_id, "passed", 8, mock_datetime)
    add_report_metric(db_path, session_id, "failed", 2, mock_datetime)

    # Query and verify
    results = export_results(db_path, session_id=session_id)
    assert len(results) == 1
    session = results[0]

    # Verify metrics
    metrics = {m["type"]: m["value"] for m in session["metrics"]}
    assert metrics["collected"] == 10
    assert metrics["passed"] == 8
    assert metrics["failed"] == 2


def test_edge_cases(db_path, mock_datetime):
    """Test edge cases and error handling."""
    # Test querying non-existent session
    results = export_results(db_path, session_id=999)
    assert len(results) == 0

    # Test querying with invalid time range
    results = export_results(
        db_path, start_time=mock_datetime + timedelta(days=1), end_time=mock_datetime
    )
    assert len(results) == 0

    # Test adding test result to non-existent session
    with pytest.raises(sqlite3.IntegrityError):
        add_test_result(
            db_path,
            session_id=999,
            test_id="test1",
            outcome="passed",
            timestamp=mock_datetime,
        )

    # Test duplicate test results (same session, test_id, timestamp)
    session_id = add_session(db_path, mock_datetime)
    add_test_result(db_path, session_id, "test1", "passed", mock_datetime)

    with pytest.raises(sqlite3.IntegrityError):
        add_test_result(
            db_path,
            session_id,
            "test1",
            "failed",  # Different outcome but same session, test_id, timestamp
            mock_datetime,
        )
