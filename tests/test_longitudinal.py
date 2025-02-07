"""Unit tests for longitudinal analysis functionality."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest
from pytest_mock import MockerFixture

from pytest_oof.utils import (
    LongitudinalAnalysis,
    ReportBasedStats,
    Results,
    SessionMetadata,
    TestHistory,
    TestResult,
    TestSessionStats,
)


@pytest.fixture
def mock_test_result(mocker: MockerFixture) -> TestResult:
    """Fixture to create a mock test result."""
    return TestResult(
        nodeid="test_1",
        outcome="passed",
        duration=0.1,
        longreprtext=None,
        capstdout="",
        capstderr="",
        caplog="",
        has_warning=False,
        start_time=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_session_metadata(mocker: MockerFixture) -> SessionMetadata:
    """Fixture to create mock session metadata."""
    return SessionMetadata(
        session_id="test-session",
        start_time=datetime.now(timezone.utc),
        stop_time=datetime.now(timezone.utc) + timedelta(seconds=1),
        duration=timedelta(seconds=1),
        sut_id="test-sut",
        sut_type="test",
        sut_version="1.0",
        sut_environment="test",
        sut_metadata={},
    )


@pytest.fixture
def mock_results(
    mocker: MockerFixture,
    mock_test_result: TestResult,
    mock_session_metadata: SessionMetadata,
) -> Results:
    """Fixture to create mock test results."""
    return Results(
        session_metadata=mock_session_metadata,
        session_stats=TestSessionStats(),
        report_stats=ReportBasedStats(),
        test_results=[mock_test_result],
        warnings=[],
        rerun_test_groups=[],
    )


@pytest.fixture
def create_test_results():
    """Create a test results object with the given parameters."""

    def _create_results(
        session_id: str = "test_session",
        sut_id: str = "",
        sut_type: str = "",
        sut_version: str = "",
        sut_environment: str = "",
        sut_metadata: Dict[str, Any] = None,
        start_time: Optional[datetime] = None,
        duration: Optional[timedelta] = None,
        test_results: Optional[List[Tuple[str, str]]] = None,
    ) -> Results:
        if sut_metadata is None:
            sut_metadata = {}
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        if duration is None:
            duration = timedelta(seconds=1)

        stop_time = start_time + duration

        metadata = SessionMetadata(
            session_id=session_id,
            sut_id=sut_id,
            sut_type=sut_type,
            sut_version=sut_version,
            sut_environment=sut_environment,
            sut_metadata=sut_metadata,
            start_time=start_time,
            stop_time=stop_time,
            duration=duration,
        )

        # Create test results collection
        test_results_collection = Results(
            session_metadata=SessionMetadata(
                session_id="test_session",
                start_time=datetime.now(),
                stop_time=datetime.now(),
                duration=timedelta(seconds=0)
            ),
            session_stats=TestSessionStats(),
            report_stats=ReportBasedStats(),
            test_results=[]
        )

        if test_results:
            for nodeid, outcome in test_results:
                test_result = TestResult(
                    nodeid=nodeid,
                    outcome=outcome,
                    start_time=start_time,
                    duration=duration.total_seconds(),
                    has_warning=False,
                )
                test_results_collection.test_results.append(test_result)

                # Update session stats
                test_results_collection.session_stats.num_tests += 1
                if outcome == "PASSED":
                    test_results_collection.session_stats.num_passes += 1
                elif outcome == "FAILED":
                    test_results_collection.session_stats.num_failures += 1
                elif outcome == "SKIPPED":
                    test_results_collection.session_stats.num_skips += 1
                elif outcome == "XFAIL":
                    test_results_collection.session_stats.num_xfails += 1
                elif outcome == "XPASS":
                    test_results_collection.session_stats.num_xpasses += 1
                elif outcome == "ERROR":
                    test_results_collection.session_stats.num_errors += 1
                elif outcome == "RERUN":
                    test_results_collection.session_stats.num_reruns += 1
        else:
            # Create a default test result
            test_result = TestResult(
                nodeid="test_example",
                outcome="PASSED",
                start_time=start_time,
                duration=duration.total_seconds(),
                has_warning=False,
            )
            test_results_collection.test_results = [test_result]
            test_results_collection.session_stats.num_tests = 1
            test_results_collection.session_stats.num_passes = 1

        return Results(
            session_metadata=metadata,
            test_results=test_results_collection.test_results,
            session_stats=test_results_collection.session_stats,
            report_stats=ReportBasedStats(),
            warnings=[],
            rerun_test_groups=[],
        )

    return _create_results


def test_get_test_status_changes(mocker: MockerFixture):
    """Test that test status changes are correctly identified."""
    # Create test history with multiple sessions
    history = TestHistory()
    base_time = datetime.now(timezone.utc)

    # Mock three sessions with different test outcomes
    sessions = []
    test_outcomes = [
        [("test_1", "passed"), ("test_2", "passed")],  # Session 1
        [("test_1", "passed"), ("test_2", "failed")],  # Session 2
        [("test_1", "failed"), ("test_2", "passed")],  # Session 3
    ]

    for i, outcomes in enumerate(test_outcomes):
        session_metadata = SessionMetadata(
            session_id=f"session{i+1}",
            start_time=base_time - timedelta(days=2 - i),
            stop_time=base_time - timedelta(days=2 - i) + timedelta(seconds=1),
            duration=timedelta(seconds=1),
            sut_id="test-sut",
            sut_type="test",
            sut_version="1.0",
            sut_environment="test",
        )

        test_results = [
            TestResult(
                nodeid=nodeid,
                outcome=outcome,
                duration=0.1,
                longreprtext=None,
                capstdout="",
                capstderr="",
                caplog="",
                has_warning=False,
                start_time=base_time - timedelta(days=2 - i),
            )
            for nodeid, outcome in outcomes
        ]

        session = Results(
            session_metadata=session_metadata,
            session_stats=TestSessionStats(),
            report_stats=ReportBasedStats(),
            test_results=test_results,
            warnings=[],
            rerun_test_groups=[],
        )
        history.add_run(session)

    # Create the analysis object
    analysis = LongitudinalAnalysis(history)

    # Mock datetime.now to return a fixed time
    mocker.patch("pytest_oof.utils.datetime", **{"now.return_value": base_time})

    # Get test status changes
    changes = analysis.get_test_status_changes()

    # Verify the changes
    assert len(changes) == 2  # Both test_1 and test_2 had changes
    assert changes["test_1"][-1]["outcome"] == "failed"  # Last outcome was failed
    assert changes["test_2"][-1]["outcome"] == "passed"  # Last outcome was passed


def test_compare_sessions(mocker: MockerFixture):
    """Test that session comparison works correctly."""
    history = TestHistory()
    base_time = datetime.now(timezone.utc)

    # Mock two sessions with different test sets
    session1_metadata = SessionMetadata(
        session_id="session1",
        start_time=base_time - timedelta(days=1),
        stop_time=base_time - timedelta(days=1) + timedelta(seconds=1),
        duration=timedelta(seconds=1),
        sut_id="test-sut",
        sut_type="test",
        sut_version="1.0",
        sut_environment="test",
    )

    session1_results = [
        TestResult(
            nodeid=f"test_{i}",
            outcome="passed",
            duration=0.1,
            longreprtext=None,
            capstdout="",
            capstderr="",
            caplog="",
            has_warning=False,
            start_time=base_time - timedelta(days=1),
        )
        for i in range(1, 4)  # test_1, test_2, test_3
    ]

    session1 = Results(
        session_metadata=session1_metadata,
        session_stats=TestSessionStats(),
        report_stats=ReportBasedStats(),
        test_results=session1_results,
        warnings=[],
        rerun_test_groups=[],
    )
    history.add_run(session1)

    # Session 2: Different test set (test_2, test_3, test_4)
    session2_metadata = SessionMetadata(
        session_id="session2",
        start_time=base_time,
        stop_time=base_time + timedelta(seconds=1),
        duration=timedelta(seconds=1),
        sut_id="test-sut",
        sut_type="test",
        sut_version="1.0",
        sut_environment="test",
    )

    session2_results = [
        TestResult(
            nodeid=f"test_{i}",
            outcome="passed",
            duration=0.1,
            longreprtext=None,
            capstdout="",
            capstderr="",
            caplog="",
            has_warning=False,
            start_time=base_time,
        )
        for i in range(2, 5)  # test_2, test_3, test_4
    ]

    session2 = Results(
        session_metadata=session2_metadata,
        session_stats=TestSessionStats(),
        report_stats=ReportBasedStats(),
        test_results=session2_results,
        warnings=[],
        rerun_test_groups=[],
    )
    history.add_run(session2)

    # Create the analysis object
    analysis = LongitudinalAnalysis(history)

    # Mock datetime.now
    mocker.patch("pytest_oof.utils.datetime", **{"now.return_value": base_time})

    # Compare the sessions
    comparison = analysis.compare_test_sets("session1", "session2")

    # Verify the comparison
    assert "test_1" in comparison["unique_to_session1"]  # Only in session 1
    assert "test_4" in comparison["unique_to_session2"]  # Only in session 2
    assert all(test in comparison["common"] for test in ["test_2", "test_3"])  # In both


def test_get_test_trends(mocker: MockerFixture):
    """Test that trend statistics are calculated correctly."""
    history = TestHistory()
    base_time = datetime.now(timezone.utc)

    # Mock three sessions over three days
    for i in range(3):
        session_metadata = SessionMetadata(
            session_id=f"session{i+1}",
            start_time=base_time - timedelta(days=2 - i),
            stop_time=base_time - timedelta(days=2 - i) + timedelta(seconds=1),
            duration=timedelta(seconds=1),
            sut_id="test-sut",
            sut_type="test",
            sut_version="1.0",
            sut_environment="test",
        )

        # Create a mix of test outcomes
        test_results = [
            TestResult(
                nodeid=f"test_{j}",
                outcome=outcome,
                duration=0.1,
                longreprtext=None,
                capstdout="",
                capstderr="",
                caplog="",
                has_warning=False,
                start_time=base_time - timedelta(days=2 - i),
            )
            for j, outcome in enumerate(["PASSED", "FAILED", "SKIPPED", "PASSED"], 1)
        ]

        # Create session stats
        session_stats = TestSessionStats()
        session_stats.num_tests = 4
        session_stats.num_passes = 2
        session_stats.num_failures = 1
        session_stats.num_skips = 1

        # Create report stats
        report_stats = ReportBasedStats()
        report_stats.num_tests = 4
        report_stats.num_passes = 2
        report_stats.num_failures = 1
        report_stats.num_skips = 1

        session = Results(
            session_metadata=session_metadata,
            session_stats=session_stats,
            report_stats=report_stats,
            test_results=test_results,
            warnings=[],
            rerun_test_groups=[],
        )
        history.add_run(session)

    # Create the analysis object
    analysis = LongitudinalAnalysis(history)

    # Mock datetime.now
    mocker.patch("pytest_oof.utils.datetime", **{"now.return_value": base_time})

    # Get trend statistics
    trends = analysis.get_trend_stats(window_size=timedelta(days=1))

    # Verify the trends
    assert len(trends) > 0
    for trend in trends:
        assert trend["num_tests"] == 4
        assert trend["num_passes"] == 2
        assert trend["num_failures"] == 1
        assert trend["num_skips"] == 1


def test_find_test_changes(mocker: MockerFixture):
    """Test that recent test changes are correctly identified."""
    history = TestHistory()
    base_time = datetime.now(timezone.utc)

    # Mock three sessions with changing test outcomes
    sessions = []
    test_outcomes = [
        [
            ("test_1", "PASSED"),
            ("test_2", "PASSED"),
            ("test_3", "PASSED"),
        ],  # Initial state
        [
            ("test_1", "FAILED"),
            ("test_2", "PASSED"),
            ("test_3", "FAILED"),
        ],  # Some changes
        [
            ("test_1", "PASSED"),
            ("test_2", "FAILED"),
            ("test_3", "FAILED"),
        ],  # More changes
    ]

    for i, outcomes in enumerate(test_outcomes):
        session_metadata = SessionMetadata(
            session_id=f"session{i+1}",
            start_time=base_time - timedelta(days=2 - i),
            stop_time=base_time - timedelta(days=2 - i) + timedelta(seconds=1),
            duration=timedelta(seconds=1),
            sut_id="test-sut",
            sut_type="test",
            sut_version="1.0",
            sut_environment="test",
        )

        test_results = [
            TestResult(
                nodeid=nodeid,
                outcome=outcome,
                duration=0.1,
                longreprtext=None,
                capstdout="",
                capstderr="",
                caplog="",
                has_warning=False,
                start_time=base_time - timedelta(days=2 - i),
            )
            for nodeid, outcome in outcomes
        ]

        # Create session stats
        session_stats = TestSessionStats()
        session_stats.num_tests = len(test_results)
        session_stats.num_passes = len(
            [t for t in test_results if t.outcome == "PASSED"]
        )
        session_stats.num_failures = len(
            [t for t in test_results if t.outcome == "FAILED"]
        )

        # Create report stats
        report_stats = ReportBasedStats()
        report_stats.num_tests = len(test_results)
        report_stats.num_passes = len(
            [t for t in test_results if t.outcome == "PASSED"]
        )
        report_stats.num_failures = len(
            [t for t in test_results if t.outcome == "FAILED"]
        )

        session = Results(
            session_metadata=session_metadata,
            session_stats=session_stats,
            report_stats=report_stats,
            test_results=test_results,
            warnings=[],
            rerun_test_groups=[],
        )
        history.add_run(session)

    # Create the analysis object
    analysis = LongitudinalAnalysis(history)

    # Mock datetime.now
    mocker.patch("pytest_oof.utils.datetime", **{"now.return_value": base_time})

    # Find recent test changes
    changes = analysis.find_test_changes(last_n_sessions=2)

    # Verify the changes
    assert "test_2" in changes["new_failures"]  # Failed in the latest session
    assert "test_1" in changes["new_passes"]  # Fixed in the latest session
    assert "test_1" in changes["intermittent"]  # Changed multiple times


def test_get_sut_runs(create_test_results):
    """Test filtering test runs by SUT parameters."""
    # Add runs with different SUT configurations
    run1 = create_test_results(
        session_id="1",
        sut_id="app1",
        sut_type="web",
        sut_version="1.0.0",
        sut_environment="prod",
    )
    run2 = create_test_results(
        session_id="2",
        sut_id="app1",
        sut_type="web",
        sut_version="1.0.1",
        sut_environment="prod",
    )
    run3 = create_test_results(
        session_id="3",
        sut_id="app2",
        sut_type="api",
        sut_version="1.0.0",
        sut_environment="staging",
    )

    history = TestHistory()
    for run in [run1, run2, run3]:
        history.add_run(run)

    # Test single parameter filtering
    assert len(history.get_sut_runs(sut_id="app1")) == 2
    assert len(history.get_sut_runs(sut_type="web")) == 2
    assert len(history.get_sut_runs(sut_version="1.0.0")) == 2
    assert len(history.get_sut_runs(sut_environment="staging")) == 1

    # Test multiple parameter filtering (AND logic)
    assert len(history.get_sut_runs(sut_id="app1", sut_version="1.0.0")) == 1
    assert (
        len(history.get_sut_runs(sut_id="app1", sut_type="web", sut_version="1.0.1"))
        == 1
    )
    assert len(history.get_sut_runs(sut_id="app2", sut_environment="prod")) == 0

    # Test with non-matching parameters
    assert len(history.get_sut_runs(sut_id="non-existent")) == 0
    assert len(history.get_sut_runs(sut_version="2.0.0")) == 0

    # Test with empty parameters (should return all runs)
    assert len(history.get_sut_runs()) == 3


def test_longitudinal_analysis_sut_aware(create_test_results):
    """Test that LongitudinalAnalysis correctly filters by SUT."""
    # Create runs with different SUT configurations
    run1 = create_test_results(
        session_id="1",
        sut_id="app1",
        sut_version="1.0.0",
        test_results=[("test1", "PASSED"), ("test2", "FAILED")],
    )
    run2 = create_test_results(
        session_id="2",
        sut_id="app1",
        sut_version="1.0.1",
        test_results=[("test1", "PASSED"), ("test2", "PASSED")],
    )
    run3 = create_test_results(
        session_id="3",
        sut_id="app2",
        sut_version="1.0.0",
        test_results=[("test1", "FAILED"), ("test2", "FAILED")],
    )

    history = TestHistory()
    for run in [run1, run2, run3]:
        history.add_run(run)

    # Create analyzers for different SUTs
    analyzer1 = LongitudinalAnalysis(history, sut_id="app1")
    analyzer2 = LongitudinalAnalysis(history, sut_id="app2")
    analyzer3 = LongitudinalAnalysis(history, sut_id="app1", sut_version="1.0.0")

    # Test get_test_status_changes
    changes1 = analyzer1.get_test_status_changes()
    assert len(changes1) == 2  # Should have history for both tests
    assert len(changes1["test1"]) == 2  # Should have 2 runs for app1
    assert len(changes1["test2"]) == 2

    changes2 = analyzer2.get_test_status_changes()
    assert len(changes2) == 2
    assert len(changes2["test1"]) == 1  # Should have 1 run for app2
    assert len(changes2["test2"]) == 1

    changes3 = analyzer3.get_test_status_changes()
    assert len(changes3) == 2
    assert len(changes3["test1"]) == 1  # Should have 1 run for app1 v1.0.0
    assert len(changes3["test2"]) == 1

    # Test compare_test_sets
    comparison = analyzer1.compare_test_sets("1", "2")
    assert "error" not in comparison
    assert len(comparison["common"]) == 2
    assert len(comparison["unique_to_session1"]) == 0
    assert len(comparison["unique_to_session2"]) == 0

    # Test with mismatched session IDs
    comparison = analyzer1.compare_test_sets("1", "3")
    assert "error" in comparison  # Session 3 belongs to app2

    # Test find_test_changes
    changes = analyzer1.find_test_changes()
    assert "test2" in changes["new_passes"]  # test2 changed from FAILED to PASSED

    # Test get_trend_stats
    stats = analyzer1.get_trend_stats(window_size=timedelta(days=1))
    assert len(stats) > 0
    assert stats[0]["num_runs"] > 0


def test_history_size_limit(create_test_results):
    """Test that TestHistory correctly limits the number of runs."""
    history = TestHistory()

    # Create 5 test runs with different timestamps
    base_time = datetime.now(timezone.utc)
    for i in range(5):
        results = create_test_results(
            session_id=f"session_{i}",
            start_time=base_time + timedelta(minutes=i),
            sut_id=f"sut_{i}",
        )
        history.add_run(results)

    # Verify we have all 5 runs
    assert len(history.results) == 5

    # Limit to 3 runs
    history.limit_runs(3)

    # Verify we kept the 3 most recent runs
    assert len(history.results) == 3
    assert [r.session_metadata.session_id for r in history.results] == [
        "session_2",
        "session_3",
        "session_4",
    ]

    # Add two more runs
    for i in range(5, 7):
        results = create_test_results(
            session_id=f"session_{i}",
            start_time=base_time + timedelta(minutes=i),
            sut_id=f"sut_{i}",
        )
        history.add_run(results)
        history.limit_runs(3)  # Apply limit after each add

    # Verify we still have only the 3 most recent runs
    assert len(history.results) == 3
    assert [r.session_metadata.session_id for r in history.results] == [
        "session_4",
        "session_5",
        "session_6",
    ]
