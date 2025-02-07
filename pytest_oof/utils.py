"""Utility classes and functions for pytest-oof."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pytest_oof.db import db_connection

logger = logging.getLogger(__name__)

import random
import time
import uuid

from pytest_oof import _project_root


def generate_timestamp_uuid():
    # Get the current timestamp in milliseconds
    timestamp = int(time.time() * 1000)
    # Generate a random 16-bit integer (to add some randomness to avoid collisions)
    random_part = random.getrandbits(64)
    # Combine timestamp and random part
    combined = (timestamp << 64) | random_part
    # Convert the combined value to a UUID
    timestamp_uuid = uuid.UUID(int=combined)

    return str(timestamp_uuid)


@dataclass
class SessionMetadata:
    """
    'Metadata': metadata about the test run, including system under test (SUT) identification
    and test session timing information.

    Fields:
        session_id: Unique identifier for the test session
        sut_id: Unique identifier for the system under test
        sut_type: Type/category of the system (e.g., "GEMS", "production", "staging")
        sut_version: Version information about the system
        sut_environment: Environment details (e.g., "prod", "staging", "dev")
        sut_metadata: Additional SUT-specific metadata
        start_time: Start time of the test session
        stop_time: End time of the test session
        duration: Duration of the test session
        python_version: Python version used for running tests
        os_info: Operating system information
        pytest_version: Pytest version used for running tests
        command_line: Command line used to run tests
    """

    session_id: str
    start_time: datetime
    stop_time: datetime
    duration: timedelta
    sut_id: str = ""
    sut_type: str = ""
    sut_version: str = ""
    sut_environment: str = ""
    sut_metadata: Dict[str, Any] = field(default_factory=dict)
    python_version: str = ""
    os_info: str = ""
    pytest_version: str = ""
    command_line: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sut_id": self.sut_id,
            "sut_type": self.sut_type,
            "sut_version": self.sut_version,
            "sut_environment": self.sut_environment,
            "sut_metadata": self.sut_metadata,
            "start_time": self.start_time.isoformat(),
            "stop_time": self.stop_time.isoformat(),
            "duration": self.duration.total_seconds(),
            "python_version": self.python_version,
            "os_info": self.os_info,
            "pytest_version": self.pytest_version,
            "command_line": self.command_line,
        }


@dataclass
class TestSessionStats:
    """
    'TestSessionStats': cumulative statistics for the entire test session
    """

    num_tests: int = 0  # Total number of test runs including reruns
    num_tests_without_rerun: int = 0  # Number of unique tests (excluding reruns)
    num_tests_total: int = 0  # Total number of tests including deselected
    num_passes: int = 0
    num_failures: int = 0
    num_errors: int = 0
    num_skips: int = 0
    num_xfails: int = 0
    num_xpasses: int = 0
    num_reruns: int = 0
    num_rerun_groups: int = 0  # Number of distinct test groups that had reruns
    num_warnings: int = 0
    num_warnings_unique: int = 0
    num_deselected: int = 0  # Number of tests deselected via pytest's test selection

    def to_dict(self) -> Dict[str, int]:
        return {
            "num_tests": self.num_tests,
            "num_tests_without_rerun": self.num_tests_without_rerun,
            "num_tests_total": self.num_tests_total,
            "num_passes": self.num_passes,
            "num_failures": self.num_failures,
            "num_errors": self.num_errors,
            "num_skips": self.num_skips,
            "num_xfails": self.num_xfails,
            "num_xpasses": self.num_xpasses,
            "num_reruns": self.num_reruns,
            "num_rerun_groups": self.num_rerun_groups,
            "num_warnings": self.num_warnings,
            "num_warnings_unique": self.num_warnings_unique,
            "num_deselected": self.num_deselected,
        }


@dataclass
class ReportBasedStats:
    """Stats collected directly from pytest test reports."""

    num_tests: int = 0  # Total number of test runs
    num_tests_total: int = 0  # Total number of tests including deselected
    num_passes: int = 0
    num_failures: int = 0
    num_errors: int = 0
    num_skips: int = 0
    num_xfails: int = 0
    num_xpasses: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "num_tests": self.num_tests,
            "num_tests_total": self.num_tests_total,
            "num_passes": self.num_passes,
            "num_failures": self.num_failures,
            "num_errors": self.num_errors,
            "num_skips": self.num_skips,
            "num_xfails": self.num_xfails,
            "num_xpasses": self.num_xpasses,
        }


@dataclass
class TestResult:
    """'TestResult': a single test result, which is a single test run of a single test.

    Fields:
    'nodeid': pytest 'node_id' (test identifier)
    'outcome': outcome of the test (PASSED, FAILED, SKIPPED, etc.)
    'start_time': datetime object for the start time of the test
    'duration': duration of the test in microseconds
    'error_message': error message if test failed
    'error_type': type of error if test failed
    'error_traceback': error traceback if test failed
    'has_warning': whether the test resulted in a warning
    'longreprtext': full representation of test failure or error
    """

    sut_id: str = ""
    sut_metadata: Dict[str, Any] = field(default_factory=dict)
    nodeid: str = ""
    outcome: str = ""
    start_time: datetime = None
    duration: float = 0.0
    error_message: str = ""
    error_type: str = ""
    error_traceback: str = ""
    has_warning: bool = False
    longreprtext: str = ""
    caplog: str = ""
    capstdout: str = ""
    capstderr: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sut_id": self.sut_id,
            "sut_metadata": self.sut_metadata,
            "nodeid": self.nodeid,
            "outcome": self.outcome,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "duration": self.duration,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "error_traceback": self.error_traceback,
            "has_warning": self.has_warning,
            "longreprtext": self.longreprtext,
            "caplog": self.caplog,
            "capstdout": self.capstdout,
            "capstderr": self.capstderr,
        }


@dataclass
class TestResults:
    """
    A collection of TestResult objects, with convenience methods for accessing
    subsets of the collection.
    """

    session_stats: TestSessionStats = None
    test_results: List[TestResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rerun_test_groups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_stats": self.session_stats.to_dict()
            if self.session_stats
            else None,
            "test_results": [r.to_dict() for r in self.test_results],
            "warnings": self.warnings,
            "rerun_test_groups": self.rerun_test_groups,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestResults":
        session_stats = (
            TestSessionStats(**data["session_stats"])
            if data.get("session_stats")
            else None
        )
        test_results = [TestResult(**r) for r in data["test_results"]]
        warnings = data.get("warnings", [])
        rerun_test_groups = data.get("rerun_test_groups", [])
        return cls(
            session_stats=session_stats,
            test_results=test_results,
            warnings=warnings,
            rerun_test_groups=rerun_test_groups,
        )


@dataclass
class Results:
    """'Results': a collection of all data collected during a test run, made nicely
    consumable by pytest-oof.

    'session_metadata': metadata about the test session including timing and SUT info
    'session_stats': overall statistics for this test session
    'report_stats': statistics collected directly from pytest test reports
    'test_results': collection of TestResult objects for all tests in the test session
    'warnings': list of warning messages
    'rerun_test_groups': list of test groups that were rerun
    """

    session_metadata: SessionMetadata
    session_stats: TestSessionStats
    report_stats: ReportBasedStats
    test_results: List[TestResult]
    warnings: List[str] = field(default_factory=list)
    rerun_test_groups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_metadata": self.session_metadata.to_dict(),
            "session_stats": self.session_stats.to_dict(),
            "report_stats": self.report_stats.to_dict(),
            "test_results": [r.to_dict() for r in self.test_results],
            "warnings": self.warnings,
            "rerun_test_groups": self.rerun_test_groups,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Results":
        session_metadata = SessionMetadata(**data["session_metadata"])
        session_stats = TestSessionStats(**data["session_stats"])
        report_stats = ReportBasedStats(**data["report_stats"])
        test_results = [TestResult(**r) for r in data["test_results"]]
        warnings = data.get("warnings", [])
        rerun_test_groups = data.get("rerun_test_groups", [])
        return cls(
            session_metadata=session_metadata,
            session_stats=session_stats,
            report_stats=report_stats,
            test_results=test_results,
            warnings=warnings,
            rerun_test_groups=rerun_test_groups,
        )


@dataclass
class TestHistory:
    """
    Maintains a collection of Results objects from multiple test runs.
    """

    results: List[Results] = field(default_factory=list)
    path: Path = field(default=None)

    def __len__(self) -> int:
        """Return the number of test sessions."""
        return len(self.results)

    @property
    def test_sessions(self) -> "TestHistory":
        """Get all test sessions."""
        return self

    def get_sut_runs(
        self,
        sut_id: str = "",
        sut_type: str = "",
        sut_version: str = "",
        sut_environment: str = "",
    ) -> List[Results]:
        """Get test runs for a specific SUT configuration.

        All specified parameters are combined with AND logic. For example:
            get_sut_runs(sut_id="my-app", sut_version="1.0.0")
        will only return results where sut_id is "my-app" AND sut_version is "1.0.0".

        Args:
            sut_id: Filter by specific SUT identifier
            sut_type: Filter by SUT type/category
            sut_version: Filter by specific SUT version
            sut_environment: Filter by specific environment

        Returns:
            List of Results objects matching ALL specified criteria.
            If no parameters are specified, returns all results.
        """
        filtered = self.results
        if sut_id:
            filtered = [r for r in filtered if r.session_metadata.sut_id == sut_id]
        if sut_type:
            filtered = [r for r in filtered if r.session_metadata.sut_type == sut_type]
        if sut_version:
            filtered = [
                r for r in filtered if r.session_metadata.sut_version == sut_version
            ]
        if sut_environment:
            filtered = [
                r
                for r in filtered
                if r.session_metadata.sut_environment == sut_environment
            ]
        return filtered

    @property
    def total_tests(self) -> int:
        """Get total number of tests across all sessions."""
        return sum(r.session_stats.num_tests for r in self.results)

    @property
    def total_passes(self) -> int:
        """Get total number of passes across all sessions."""
        return sum(r.session_stats.num_passes for r in self.results)

    @property
    def total_failures(self) -> int:
        """Get total number of failures across all sessions."""
        return sum(r.session_stats.num_failures for r in self.results)

    @property
    def total_errors(self) -> int:
        """Get total number of errors across all sessions."""
        return sum(r.session_stats.num_errors for r in self.results)

    @property
    def total_skips(self) -> int:
        """Get total number of skips across all sessions."""
        return sum(r.session_stats.num_skips for r in self.results)

    @property
    def total_xfails(self) -> int:
        """Get total number of expected failures across all sessions."""
        return sum(r.session_stats.num_xfails for r in self.results)

    @property
    def total_xpasses(self) -> int:
        """Get total number of unexpected passes across all sessions."""
        return sum(r.session_stats.num_xpasses for r in self.results)

    @property
    def total_reruns(self) -> int:
        """Get total number of reruns across all sessions."""
        return sum(r.session_stats.num_reruns for r in self.results)

    @property
    def pass_rate(self) -> float:
        """Get pass rate across all sessions."""
        total = self.total_tests
        return self.total_passes / total if total > 0 else 0.0

    @property
    def failure_rate(self) -> float:
        """Get failure rate across all sessions."""
        total = self.total_tests
        return self.total_failures / total if total > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Get error rate across all sessions."""
        total = self.total_tests
        return self.total_errors / total if total > 0 else 0.0

    @property
    def skip_rate(self) -> float:
        """Get skip rate across all sessions."""
        total = self.total_tests
        return self.total_skips / total if total > 0 else 0.0

    @property
    def xfail_rate(self) -> float:
        """Get expected failure rate across all sessions."""
        total = self.total_tests
        return self.total_xfails / total if total > 0 else 0.0

    @property
    def xpass_rate(self) -> float:
        """Get unexpected pass rate across all sessions."""
        total = self.total_tests
        return self.total_xpasses / total if total > 0 else 0.0

    def find_test_changes(self) -> Dict[str, List[str]]:
        """Find tests that have changed status."""
        return {"new_failures": [], "new_passes": [], "intermittent": []}

    def load_test_results(
        self,
        sut_id: Optional[str] = None,
        sut_type: Optional[str] = None,
        sut_version: Optional[str] = None,
        sut_env: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        last_n_sessions: Optional[int] = None,
        outcome: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> None:
        """Load test results from the database."""
        if not self.path:
            raise ValueError("No database path set")

        with db_connection(self.path) as conn:
            c = conn.cursor()

            # Get test sessions
            query = """
                SELECT
                    id,
                    start_time,
                    end_time,
                    duration,
                    sut_id,
                    sut_type,
                    sut_version,
                    sut_env,
                    python_version,
                    os_info,
                    pytest_version,
                    command_line,
                    num_tests,
                    num_passes,
                    num_failures,
                    num_errors,
                    num_skips,
                    num_xfails,
                    num_xpasses,
                    num_reruns,
                    num_rerun_groups,
                    num_warnings
                FROM test_sessions ts
                WHERE 1=1
            """
            params = []

            # Add filters
            if sut_id:
                query += " AND ts.sut_id = ?"
                params.append(sut_id)
            if sut_type:
                query += " AND ts.sut_type = ?"
                params.append(sut_type)
            if sut_version:
                query += " AND ts.sut_version = ?"
                params.append(sut_version)
            if sut_env:
                query += " AND ts.sut_env = ?"
                params.append(sut_env)
            if start_time:
                query += " AND ts.start_time >= ?"
                params.append(start_time)
            if end_time:
                query += " AND ts.start_time <= ?"
                params.append(end_time)

            # Add order by and limit
            query += " ORDER BY ts.start_time DESC"
            if last_n_sessions:
                query += " LIMIT ?"
                params.append(last_n_sessions)

            # Execute query
            c.execute(query, params)
            rows = c.fetchall()

            # Clear existing results
            self.results.clear()

            # Process each session
            for row in rows:
                session_id = row[0]
                start_time = (
                    datetime.fromisoformat(row[1]) if row[1] else datetime.now()
                )
                end_time = datetime.fromisoformat(row[2]) if row[2] else datetime.now()
                duration = timedelta(seconds=row[3] or 0)

                session_metadata = SessionMetadata(
                    session_id=str(session_id),
                    start_time=start_time,
                    stop_time=end_time,
                    duration=duration,
                    sut_id=row[4] or "",
                    sut_type=row[5] or "",
                    sut_version=row[6] or "",
                    sut_environment=row[7] or "",
                    python_version=row[8] or "",
                    os_info=row[9] or "",
                    pytest_version=row[10] or "",
                    command_line=row[11] or "",
                )

                # Create session stats from database values
                session_stats = TestSessionStats(
                    num_tests=row[12] or 0,
                    num_passes=row[13] or 0,
                    num_failures=row[14] or 0,
                    num_errors=row[15] or 0,
                    num_skips=row[16] or 0,
                    num_xfails=row[17] or 0,
                    num_xpasses=row[18] or 0,
                    num_reruns=row[19] or 0,
                    num_rerun_groups=row[20] or 0,
                    num_warnings=row[21] or 0,
                )

                # Create Results object and add to history
                result = Results(
                    session_metadata=session_metadata,
                    session_stats=session_stats,
                    report_stats=ReportBasedStats(),  # Empty report stats since we use session stats
                    test_results=[],  # We'll populate this next
                )

                # Get test results for this session
                test_query = """
                    SELECT
                        test_id,
                        outcome,
                        timestamp,
                        duration,
                        error_message,
                        error_type,
                        error_traceback,
                        has_warning,
                        longreprtext
                    FROM test_results
                    WHERE session_id = ?
                """
                test_params = [session_id]

                if outcome:
                    test_query += " AND outcome = ?"
                    test_params.append(outcome)
                if test_id:
                    test_query += " AND test_id = ?"
                    test_params.append(test_id)

                c.execute(test_query, test_params)
                test_rows = c.fetchall()

                # Process test results
                for test_row in test_rows:
                    test_result = TestResult(
                        nodeid=test_row[0],
                        outcome=test_row[1],
                        start_time=datetime.fromisoformat(test_row[2])
                        if test_row[2]
                        else None,
                        duration=test_row[3] or 0.0,
                        error_message=test_row[4] or "",
                        error_type=test_row[5] or "",
                        error_traceback=test_row[6] or "",
                        has_warning=bool(test_row[7]),
                        longreprtext=test_row[8] or "",
                    )
                    result.test_results.append(test_result)

                self.results.append(result)

    def add_run(self, result: Results) -> None:
        """Add a test run to the history."""
        self.results.append(result)

    def limit_runs(self, max_runs: int) -> None:
        """Limit the number of runs in history to max_runs, keeping the most recent."""
        if len(self.results) > max_runs:
            self.results = self.results[-max_runs:]

    def get_runs(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Results]:
        """Get test runs within the specified time range."""
        filtered = self.results
        if start_time:
            filtered = [
                r for r in filtered if r.session_metadata.start_time >= start_time
            ]
        if end_time:
            filtered = [
                r for r in filtered if r.session_metadata.start_time <= end_time
            ]
        return filtered

    def get_sut_runs(
        self,
        sut_id: str = "",
        sut_type: str = "",
        sut_version: str = "",
        sut_environment: str = "",
    ) -> List[Results]:
        """Get test runs for a specific SUT configuration.

        All specified parameters are combined with AND logic. For example:
            get_sut_runs(sut_id="my-app", sut_version="1.0.0")
        will only return results where sut_id is "my-app" AND sut_version is "1.0.0".

        Args:
            sut_id: Filter by specific SUT identifier
            sut_type: Filter by SUT type/category
            sut_version: Filter by specific SUT version
            sut_environment: Filter by specific environment

        Returns:
            List of Results objects matching ALL specified criteria.
            If no parameters are specified, returns all results.
        """
        filtered = self.results
        if sut_id:
            filtered = [r for r in filtered if r.session_metadata.sut_id == sut_id]
        if sut_type:
            filtered = [r for r in filtered if r.session_metadata.sut_type == sut_type]
        if sut_version:
            filtered = [
                r for r in filtered if r.session_metadata.sut_version == sut_version
            ]
        if sut_environment:
            filtered = [
                r
                for r in filtered
                if r.session_metadata.sut_environment == sut_environment
            ]
        return filtered

    def get_latest_run(self) -> Optional[Results]:
        """Get the most recent test run."""
        if not self.results:
            return None
        return max(self.results, key=lambda r: r.session_metadata.start_time)

    def save(self, file_path: Path) -> None:
        """Save test history to a file."""
        with open(file_path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, file_path: Path) -> "TestHistory":
        """Load test history from a file."""
        with open(file_path, "rb") as f:
            return pickle.load(f)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class LongitudinalAnalysis:
    """
    Provides longitudinal (over time) analysis capabilities for test histories.
    This class helps answer questions about test trends, changes, and patterns
    across multiple test sessions for a single SUT.
    """

    history: TestHistory
    sut_id: str = ""
    sut_type: str = ""
    sut_version: str = ""
    sut_environment: str = ""

    def _get_filtered_runs(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Results]:
        """Get test runs filtered by SUT and time range."""
        runs = self.history.get_sut_runs(
            sut_id=self.sut_id,
            sut_type=self.sut_type,
            sut_version=self.sut_version,
            sut_environment=self.sut_environment,
        )
        if start_time:
            runs = [r for r in runs if r.session_metadata.start_time >= start_time]
        if end_time:
            runs = [r for r in runs if r.session_metadata.start_time <= end_time]
        return runs

    def get_test_status_changes(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Track how test outcomes have changed over time.
        Returns a dict mapping test nodeids to their outcome history.
        """
        runs = self._get_filtered_runs(start_time, end_time)
        if not runs:
            return {}

        test_history = {}
        for run in sorted(runs, key=lambda r: r.session_metadata.start_time):
            for test in run.test_results:
                if test.nodeid not in test_history:
                    test_history[test.nodeid] = []
                test_history[test.nodeid].append(
                    {
                        "time": run.session_metadata.start_time,
                        "outcome": test.outcome,
                        "duration": test.duration,
                    }
                )

        return test_history

    def compare_test_sets(
        self, session_id1: str, session_id2: str
    ) -> Dict[str, List[str]]:
        """
        Compare test sets between two sessions to find:
        - Tests unique to session1
        - Tests unique to session2
        - Tests common to both sessions
        """
        runs = self._get_filtered_runs()
        run1 = next(
            (r for r in runs if r.session_metadata.session_id == session_id1), None
        )
        run2 = next(
            (r for r in runs if r.session_metadata.session_id == session_id2), None
        )

        if not run1 or not run2:
            return {"error": ["One or both session IDs not found in the specified SUT"]}

        tests1 = {t.nodeid for t in run1.test_results}
        tests2 = {t.nodeid for t in run2.test_results}

        return {
            "unique_to_session1": sorted(list(tests1 - tests2)),
            "unique_to_session2": sorted(list(tests2 - tests1)),
            "common": sorted(list(tests1 & tests2)),
        }

    def find_test_changes(self, last_n_sessions: int = 1) -> Dict[str, List[str]]:
        """
        Find tests that have changed status in recent sessions compared to their history.
        A test is considered changed if its outcome differs from its most common outcome
        in previous sessions.
        """
        changes = {"new_failures": [], "new_passes": [], "intermittent": []}

        # Get recent test runs
        runs = self._get_filtered_runs()
        if not runs:
            return changes

        # Sort runs by time and get the latest N sessions
        sorted_runs = sorted(runs, key=lambda r: r.session_metadata.start_time)
        if len(sorted_runs) <= last_n_sessions:
            return changes

        latest_runs = sorted_runs[-last_n_sessions:]
        history_runs = sorted_runs[:-last_n_sessions]  # Exclude latest N sessions

        # Build test history
        test_history = {}
        for run in history_runs:
            for test in run.test_results:
                if test.nodeid not in test_history:
                    test_history[test.nodeid] = []
                test_history[test.nodeid].append(test.outcome.lower())

        # Process latest sessions
        latest_history = {}
        for run in latest_runs[:-1]:  # All but the last session
            for test in run.test_results:
                if test.nodeid not in latest_history:
                    latest_history[test.nodeid] = []
                latest_history[test.nodeid].append(test.outcome.lower())

        # Get outcomes from the very latest session
        latest_outcomes = {}
        latest_session = latest_runs[-1]
        for test in latest_session.test_results:
            latest_outcomes[test.nodeid] = test.outcome.lower()

        # Check for changes
        for test_id, current_outcome in latest_outcomes.items():
            # Get historical outcomes
            hist_outcomes = test_history.get(test_id, [])
            recent_outcomes = latest_history.get(test_id, [])

            # Skip if no history
            if not hist_outcomes and not recent_outcomes:
                continue

            # Determine the most common outcome from history
            all_history = hist_outcomes + recent_outcomes
            if all_history:
                most_common = max(set(all_history), key=all_history.count)
            else:
                continue

            # Only show debug info if there's a status change
            if current_outcome != most_common:
                print(
                    f"Test {test_id}: current={current_outcome}, history={all_history}, most_common={most_common}"
                )

            # Check for status changes
            if most_common == "passed" and current_outcome == "failed":
                changes["new_failures"].append(test_id)
            elif most_common == "failed" and current_outcome == "passed":
                changes["new_passes"].append(test_id)

            # Check for intermittent behavior
            if len(set(all_history)) > 1:
                changes["intermittent"].append(test_id)

        # Remove duplicates and sort
        changes["new_failures"] = sorted(set(changes["new_failures"]))
        changes["new_passes"] = sorted(set(changes["new_passes"]))
        changes["intermittent"] = sorted(set(changes["intermittent"]))

        return changes

    def get_trend_stats(
        self, window_size: timedelta = timedelta(days=1)
    ) -> List[Dict[str, Any]]:
        """
        Calculate trend statistics over time using a sliding window.
        Returns statistics for each window period.
        """
        runs = self._get_filtered_runs()
        if not runs:
            return []

        sorted_runs = sorted(runs, key=lambda r: r.session_metadata.start_time)
        start_time = sorted_runs[0].session_metadata.start_time
        end_time = sorted_runs[-1].session_metadata.start_time

        # Create windows
        windows = []
        window_start = start_time
        while window_start <= end_time:
            window_end = window_start + window_size
            window_runs = [
                r
                for r in sorted_runs
                if window_start <= r.session_metadata.start_time < window_end
            ]

            if window_runs:
                # Helper function to safely sum stats that might be None
                def safe_sum(attr: str) -> int:
                    return sum(
                        getattr(r.session_stats, attr, 0) or 0 for r in window_runs
                    )

                stats = {
                    "window_start": window_start,
                    "window_end": window_end,
                    "num_runs": len(window_runs),
                    "num_tests": safe_sum("num_tests"),
                    "num_passes": safe_sum("num_passes"),
                    "num_failures": safe_sum("num_failures"),
                    "num_errors": safe_sum("num_errors"),
                    "num_skips": safe_sum("num_skips"),
                    "num_xfails": safe_sum("num_xfails"),
                    "num_xpasses": safe_sum("num_xpasses"),
                    "num_reruns": safe_sum("num_reruns"),
                }
                windows.append(stats)

            window_start = window_end

        return windows
