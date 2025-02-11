"""Utility classes and functions for pytest-oof."""
import json
import logging
import os
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pytest

from pytest_oof.models import (
    Results,
    TestResult,
    TestSessionStats,
    ReportBasedStats,
    SessionMetadata,
)
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
        sut_environment: Optional[str] = None,
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

            # Build session query
            session_query = """
                SELECT
                    s.id,
                    s.start_time,
                    s.stop_time,
                    s.duration,
                    s.num_tests,
                    s.num_tests_without_rerun,
                    s.num_tests_total,
                    s.num_passes,
                    s.num_failures,
                    s.num_errors,
                    s.num_skips,
                    s.num_xfails,
                    s.num_xpasses,
                    s.num_reruns,
                    s.num_rerun_groups,
                    s.num_warnings,
                    s.num_warnings_unique,
                    s.num_deselected,
                    s.sut_id,
                    s.sut_type,
                    s.sut_version,
                    s.sut_environment
                FROM test_sessions s
                WHERE 1=1
            """
            params = []

            if sut_id:
                session_query += " AND s.sut_id = ?"
                params.append(sut_id)
            if sut_type:
                session_query += " AND s.sut_type = ?"
                params.append(sut_type)
            if sut_version:
                session_query += " AND s.sut_version = ?"
                params.append(sut_version)
            if sut_environment:
                session_query += " AND s.sut_environment = ?"
                params.append(sut_environment)
            if start_time:
                session_query += " AND s.start_time >= ?"
                params.append(start_time.isoformat())
            if end_time:
                session_query += " AND s.start_time <= ?"
                params.append(end_time.isoformat())

            session_query += " ORDER BY s.start_time DESC"
            if last_n_sessions:
                session_query += " LIMIT ?"
                params.append(last_n_sessions)

            c.execute(session_query, params)
            session_rows = c.fetchall()

            # Process each session
            for session_row in session_rows:
                session_id = session_row[0]  # id is first column

                # Create session metadata
                session_metadata = SessionMetadata(
                    session_id=session_id,
                    start_time=datetime.fromisoformat(session_row[1]),
                    stop_time=datetime.fromisoformat(session_row[2]) if session_row[2] else None,
                    duration=timedelta(seconds=session_row[3]) if session_row[3] else None,
                    sut_id=session_row[18] or "",
                    sut_type=session_row[19] or "",
                    sut_version=session_row[20] or "",
                    sut_environment=session_row[21] or "",
                    python_version="",  # Not stored in DB
                    os_info="",  # Not stored in DB
                    pytest_version="",  # Not stored in DB
                    command_line="",  # Not stored in DB
                )

                # Create session stats
                session_stats = TestSessionStats(
                    num_tests=session_row[4] or 0,
                    num_tests_without_rerun=session_row[5] or 0,
                    num_tests_total=session_row[6] or 0,
                    num_passes=session_row[7] or 0,
                    num_failures=session_row[8] or 0,
                    num_errors=session_row[9] or 0,
                    num_skips=session_row[10] or 0,
                    num_xfails=session_row[11] or 0,
                    num_xpasses=session_row[12] or 0,
                    num_reruns=session_row[13] or 0,
                    num_rerun_groups=session_row[14] or 0,
                    num_warnings=session_row[15] or 0,
                    num_warnings_unique=session_row[16] or 0,
                    num_deselected=session_row[17] or 0,
                )

                # Get rerun groups for this session
                c.execute(
                    "SELECT group_name FROM rerun_groups WHERE session_id = ?",
                    (session_id,),
                )
                rerun_groups = [row[0] for row in c.fetchall()]

                # Get test results for this session
                test_query = """
                    SELECT
                        nodeid,
                        outcome,
                        start_time,
                        duration,
                        error_message,
                        error_type,
                        error_traceback,
                        caplog,
                        capstderr,
                        capstdout,
                        has_warning,
                        longreprtext,
                        rerun_count
                    FROM test_results
                    WHERE session_id = ?
                """
                test_params = [session_id]

                if outcome:
                    test_query += " AND outcome = ?"
                    test_params.append(outcome)
                if test_id:
                    test_query += " AND nodeid = ?"
                    test_params.append(test_id)

                c.execute(test_query, test_params)
                test_rows = c.fetchall()

                # Process test results
                test_results = []
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
                        caplog=test_row[7] or "",
                        capstderr=test_row[8] or "",
                        capstdout=test_row[9] or "",
                        has_warning=bool(test_row[10]),
                        longreprtext=test_row[11] or "",
                        rerun_count=test_row[12] or 0
                    )
                    test_results.append(test_result)

                # Create full Results object
                result = Results(
                    session_metadata=session_metadata,
                    session_stats=session_stats,
                    report_stats=ReportBasedStats(),
                    test_results=test_results,
                    rerun_test_groups=rerun_groups,
                )
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
            import pickle
            pickle.dump(self, f)

    @classmethod
    def load(cls, file_path: Path) -> "TestHistory":
        """Load test history from a file."""
        with open(file_path, "rb") as f:
            import pickle
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
        Calculate trend statistics over time.
        Returns statistics for each unique timestamp.
        """
        runs = self._get_filtered_runs()
        if not runs:
            return []

        # Sort runs by timestamp
        sorted_runs = sorted(runs, key=lambda r: r.session_metadata.start_time)

        # Create a stats entry for each unique timestamp
        stats_list = []
        for run in sorted_runs:
            # Helper function to safely get stats that might be None
            def safe_get(attr: str) -> int:
                return getattr(run.session_stats, attr, 0) or 0

            stats = {
                "window_start": run.session_metadata.start_time,
                "window_end": run.session_metadata.start_time + timedelta(seconds=run.session_stats.duration or 0),
                "num_runs": 1,  # Each timestamp is a unique run
                "num_tests": safe_get("num_tests"),
                "num_passes": safe_get("num_passes"),
                "num_failures": safe_get("num_failures"),
                "num_errors": safe_get("num_errors"),
                "num_skips": safe_get("num_skips"),
                "num_xfails": safe_get("num_xfails"),
                "num_xpasses": safe_get("num_xpasses"),
                "num_reruns": safe_get("num_reruns"),
            }
            stats_list.append(stats)

        return stats_list
