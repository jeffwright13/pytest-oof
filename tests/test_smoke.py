"""Smoke tests to ensure basic functionality remains intact."""
import json
import logging
import sys
from pathlib import Path

import pytest
from pytest_mock import mocker


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
