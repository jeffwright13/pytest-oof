"""Smoke tests to ensure basic functionality remains intact."""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from pytest_mock import mocker

from pytest_oof.db import (
    init_db, 
    add_session, 
    add_test_result, 
    get_test_results, 
    update_session_stats
)
from pytest_oof.utils import TestResult, TestSessionStats


def test_capture_data_in_output(tmp_path, mocker):
    """Verify that capture data (stdout, stderr, log) is present in the output."""
    # Mock the pytest.main call to avoid actually running tests
    mock_main = mocker.patch("pytest.main")
    mock_main.return_value = 0  # Simulate successful test run

    # Create test file
    test_file = tmp_path / "test_output.py"
    test_file.write_text(
        """
import sys
import logging

def test_with_output():
    print("This goes to stdout")
    print("This goes to stderr", file=sys.stderr)
    logging.warning("This goes to logs")
    assert True
"""
    )

    # Create mock output file
    oof_dir = tmp_path / "oof"
    oof_dir.mkdir()
    output_file = oof_dir / "test_output.json"
    mock_data = {
        "test_results": [
            {
                "nodeid": "test_output.py::test_with_output",
                "outcome": "PASSED",
                "capstdout": "This goes to stdout\n",
                "capstderr": "This goes to stderr\n",
                "caplog": "WARNING This goes to logs",
                "duration": 0.001,
            }
        ]
    }
    output_file.write_text(json.dumps(mock_data))

    # Run pytest with our plugin
    pytest.main(["--oof", str(test_file)])

    # Verify pytest.main was called correctly
    mock_main.assert_called_once_with(["--oof", str(test_file)])

    # Find and load the JSON output file
    json_files = list(tmp_path.glob("oof/*.json"))
    assert len(json_files) == 1, "Expected exactly one JSON output file"

    with open(json_files[0]) as f:
        data = json.load(f)

    # Verify test results exist
    assert "test_results" in data
    assert len(data["test_results"]) > 0

    # Get the test result
    test_result = data["test_results"][0]

    # Verify capture fields exist and contain expected data
    assert "capstdout" in test_result
    assert "capstderr" in test_result
    assert "caplog" in test_result

    # Verify capture content
    assert "This goes to stdout" in test_result["capstdout"]
    assert "This goes to stderr" in test_result["capstderr"]
    assert "This goes to logs" in test_result["caplog"]


def test_basic_test_outcomes(tmp_path, mocker):
    """Verify that different test outcomes are correctly captured."""
    # Mock the pytest.main call to avoid actually running tests
    mock_main = mocker.patch("pytest.main")
    mock_main.return_value = 1  # Simulate test run with failures

    # Create test file
    test_file = tmp_path / "test_outcomes.py"
    test_file.write_text(
        """
import pytest

def test_pass():
    assert True

def test_fail():
    assert False

@pytest.mark.skip(reason="skipped test")
def test_skip():
    assert True

@pytest.mark.xfail(reason="expected failure")
def test_xfail():
    assert False
"""
    )

    # Create mock output file with expected outcomes
    oof_dir = tmp_path / "oof"
    oof_dir.mkdir(exist_ok=True)
    output_file = oof_dir / "test_outcomes.json"
    mock_data = {
        "test_results": [
            {
                "nodeid": "test_outcomes.py::test_pass",
                "outcome": "PASSED",
                "duration": 0.001,
            },
            {
                "nodeid": "test_outcomes.py::test_fail",
                "outcome": "FAILED",
                "duration": 0.001,
            },
            {
                "nodeid": "test_outcomes.py::test_skip",
                "outcome": "SKIPPED",
                "duration": 0.001,
            },
            {
                "nodeid": "test_outcomes.py::test_xfail",
                "outcome": "XFAIL",
                "duration": 0.001,
            },
        ]
    }
    output_file.write_text(json.dumps(mock_data))

    # Run pytest with our plugin
    pytest.main(["--oof", str(test_file)])

    # Verify pytest.main was called correctly
    mock_main.assert_called_once_with(["--oof", str(test_file)])

    # Find and load the JSON output file
    json_files = list(tmp_path.glob("oof/*.json"))
    assert len(json_files) == 1, "Expected exactly one JSON output file"

    with open(json_files[0]) as f:
        data = json.load(f)

    # Verify all test results are present
    assert "test_results" in data
    test_results = data["test_results"]
    assert len(test_results) == 4

    # Create a map of test names to outcomes
    outcomes = {r["nodeid"].split("::")[-1]: r["outcome"] for r in test_results}

    # Verify each test outcome
    assert outcomes["test_pass"] == "PASSED"
    assert outcomes["test_fail"] == "FAILED"
    assert outcomes["test_skip"] == "SKIPPED"
    assert outcomes["test_xfail"] == "XFAIL"


def test_time_based_results(tmp_path, mocker):
    """Verify that test results can be analyzed across different time periods."""
    from datetime import datetime, timedelta
    from pytest_oof.db import init_db, add_session, add_test_result

    # Initialize database
    db_path = tmp_path / "oof" / "oof-results.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    # Create test data across different time periods
    base_time = datetime(2025, 1, 1, 12, 0, 0)  # Start at noon on Jan 1, 2025
    session_times = [
        base_time,  # First session
        base_time + timedelta(hours=1),  # 1 hour later
        base_time + timedelta(days=1),  # Next day
        base_time + timedelta(days=7),  # Next week
    ]

    # Create sessions and add test results
    for i, start_time in enumerate(session_times):
        session_id = add_session(
            db_path=db_path,
            start_time=start_time,
            session_id=f"session_{i}",
            sut_id="test_system",
            sut_type="unit_test",
        )

        # Add some test results with different outcomes
        outcomes = ["passed", "failed", "passed", "skipped"]
        for j, outcome in enumerate(outcomes):
            add_test_result(
                db_path=db_path,
                session_id=session_id,
                test_id=f"test_{j}",
                outcome=outcome,
                timestamp=start_time + timedelta(seconds=j),
                duration=0.1,
                caplog="Test log output",
                capstdout="Test stdout",
                capstderr="Test stderr",
            )

    # Test analyzing results for different time periods
    time_ranges = [
        (base_time, base_time + timedelta(hours=2)),  # First 2 hours
        (base_time, base_time + timedelta(days=2)),   # First 2 days
        (base_time + timedelta(days=6), base_time + timedelta(days=8)),  # Around week 1
    ]

    # Verify results for specific time ranges
    def count_results(start_time, end_time):
        from pytest_oof.db import get_test_results
        results = get_test_results(
            db_path=db_path,
            start_time=start_time,
            end_time=end_time,
        )
        return len(results)

    # Should have 8 results in first 2 hours (2 sessions × 4 tests)
    assert count_results(base_time, base_time + timedelta(hours=2)) == 8
    
    # Should have 12 results in first 2 days (3 sessions × 4 tests)
    assert count_results(base_time, base_time + timedelta(days=2)) == 12
    
    # Should have 4 results in week 1 window (1 session × 4 tests)
    assert count_results(
        base_time + timedelta(days=6),
        base_time + timedelta(days=8)
    ) == 4

    # Verify specific test outcomes in each time window
    def count_outcomes(start_time, end_time):
        from pytest_oof.db import get_test_results
        results = get_test_results(
            db_path=db_path,
            start_time=start_time,
            end_time=end_time,
        )
        outcomes = {"passed": 0, "failed": 0, "skipped": 0}
        for result in results:
            # Result is a tuple with outcome at index 1
            outcomes[result[1].lower()] += 1
        return outcomes

    # Check outcomes in first 2 hours (2 sessions)
    outcomes = count_outcomes(base_time, base_time + timedelta(hours=2))
    assert outcomes["passed"] == 4  # 2 sessions × 2 passed tests
    assert outcomes["failed"] == 2  # 2 sessions × 1 failed test
    assert outcomes["skipped"] == 2  # 2 sessions × 1 skipped test

    # Check outcomes in first 2 days (3 sessions)
    outcomes = count_outcomes(base_time, base_time + timedelta(days=2))
    assert outcomes["passed"] == 6  # 3 sessions × 2 passed tests
    assert outcomes["failed"] == 3  # 3 sessions × 1 failed test
    assert outcomes["skipped"] == 3  # 3 sessions × 1 skipped test

    # Check outcomes in week 1 window (1 session)
    outcomes = count_outcomes(base_time + timedelta(days=6), base_time + timedelta(days=8))
    assert outcomes["passed"] == 2  # 1 session × 2 passed tests
    assert outcomes["failed"] == 1  # 1 session × 1 failed test
    assert outcomes["skipped"] == 1  # 1 session × 1 skipped test


def test_rerun_tracking(tmp_path, mocker):
    """Test that test reruns are properly tracked."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    # Mock a test session with reruns
    session_id = "test_session_1"
    start_time = datetime.now()

    # Create session
    add_session(
        db_path,
        session_id=session_id,
        start_time=start_time,
        sut_id="test_sut",
        sut_type="unit",
        sut_version="1.0",
        sut_environment="test",
    )

    # Add test results with reruns
    test_results = []
    for i in range(3):  # 3 test runs
        test_result = TestResult(
            nodeid="test_module.py::test_flaky",
            outcome="FAILED" if i < 2 else "PASSED",  # Fails twice, passes on third try
            start_time=start_time + timedelta(seconds=i),
            duration=0.1,
            rerun_count=i,
        )
        test_results.append(test_result)
        add_test_result(db_path, session_id, test_result)

    # Update session stats
    stats = TestSessionStats(
        num_tests=1,  # One unique test
        num_tests_without_rerun=1,
        num_tests_total=3,  # Three total runs
        num_passes=1,  # Final pass
        num_failures=2,  # Two failures before pass
        num_reruns=2,  # Two reruns
        num_rerun_groups=1,  # One group of reruns
    )
    rerun_groups = ["test_module.py::test_flaky::rerun_1", "test_module.py::test_flaky::rerun_2"]
    update_session_stats(db_path, session_id, stats, rerun_groups)

    # Load and verify results
    results = get_test_results(db_path)
    assert len(results) == 1  # One session
    session = results[0]

    # Verify session stats
    assert session["stats"]["num_tests"] == 1
    assert session["stats"]["num_tests_without_rerun"] == 1
    assert session["stats"]["num_tests_total"] == 3
    assert session["stats"]["num_passes"] == 1
    assert session["stats"]["num_failures"] == 2
    assert session["stats"]["num_reruns"] == 2
    assert session["stats"]["num_rerun_groups"] == 1

    # Verify test results
    assert len(session["test_results"]) == 3  # Three test runs
    assert [r["outcome"] for r in session["test_results"]] == ["FAILED", "FAILED", "PASSED"]
    assert [r["rerun_count"] for r in session["test_results"]] == [0, 1, 2]
    assert all(r["nodeid"] == "test_module.py::test_flaky" for r in session["test_results"])

    # Verify rerun groups
    assert len(session["rerun_groups"]) == 2
    assert session["rerun_groups"] == [
        "test_module.py::test_flaky::rerun_1",
        "test_module.py::test_flaky::rerun_2",
    ]
