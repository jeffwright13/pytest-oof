"""Analyzer interface for pytest-oof test data."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pytest_oof.db import (
    db_connection,
    get_duration_trends,
    get_recent_failures,
    get_stability_metrics,
)


@dataclass
class SutStats:
    """Statistics for a specific SUT."""

    sut_id: str
    sut_type: str
    sut_version: str
    environment: str
    total_sessions: int
    total_tests: int
    total_passes: int
    total_failures: int
    total_reruns: int
    first_seen: datetime
    last_seen: datetime
    flaky_tests: List[str]  # nodeids of tests that needed reruns


@dataclass
class TestTrend:
    """Trend analysis for a specific test."""

    nodeid: str
    pass_rate: float
    failure_rate: float
    avg_reruns: float
    total_runs: int
    first_seen: datetime
    last_seen: datetime
    environments: Set[str]
    sut_versions: Set[str]


class TestDataAnalyzer:
    """High-level interface for analyzing pytest-oof test data."""

    def __init__(self, db_path: Path):
        """Initialize analyzer with database path."""
        self.db_path = Path(db_path)
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        """Ensure database directory exists."""
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """Initialize database tables."""
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            # Create sessions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS test_sessions (
                    session_id TEXT PRIMARY KEY,
                    sut_id TEXT NOT NULL,
                    sut_type TEXT,
                    sut_version TEXT,
                    sut_env TEXT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration INTEGER,
                    total_tests INTEGER DEFAULT 0,
                    passed_tests INTEGER DEFAULT 0,
                    failed_tests INTEGER DEFAULT 0,
                    skipped_tests INTEGER DEFAULT 0,
                    xfailed_tests INTEGER DEFAULT 0,
                    xpassed_tests INTEGER DEFAULT 0,
                    warnings INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    rerun INTEGER DEFAULT 0,
                    rerun_outcomes TEXT DEFAULT '[]',
                    rerun_recovery_rate REAL DEFAULT 0.0,
                    rerun_total_time REAL DEFAULT 0.0
                )
                """
            )

            # Create test_results table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    start_time TIMESTAMP,
                    duration REAL,
                    error_message TEXT,
                    error_type TEXT,
                    error_traceback TEXT,
                    has_warning BOOLEAN,
                    longreprtext TEXT,
                    caplog TEXT,
                    capstdout TEXT,
                    capstderr TEXT,
                    rerun_count INTEGER DEFAULT 0,
                    rerun_outcomes TEXT DEFAULT '[]',
                    environment TEXT,
                    warnings TEXT,
                    FOREIGN KEY (session_id) REFERENCES test_sessions(session_id)
                )
                """
            )

            # Add any missing columns
            cursor.execute("PRAGMA table_info(test_results)")
            columns = {col[1] for col in cursor.fetchall()}

            if "rerun_outcomes" not in columns:
                cursor.execute(
                    "ALTER TABLE test_results ADD COLUMN rerun_outcomes TEXT DEFAULT '[]'"
                )

            cursor.execute("PRAGMA table_info(test_sessions)")
            columns = {col[1] for col in cursor.fetchall()}

            if "rerun_outcomes" not in columns:
                cursor.execute(
                    "ALTER TABLE test_sessions ADD COLUMN rerun_outcomes TEXT DEFAULT '[]'"
                )

            if "rerun_recovery_rate" not in columns:
                cursor.execute(
                    "ALTER TABLE test_sessions ADD COLUMN rerun_recovery_rate REAL DEFAULT 0.0"
                )

            if "rerun_total_time" not in columns:
                cursor.execute(
                    "ALTER TABLE test_sessions ADD COLUMN rerun_total_time REAL DEFAULT 0.0"
                )

            conn.commit()

    def get_all_suts(self) -> List[Dict[str, str]]:
        """Get a list of all unique SUTs in the database."""
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT sut_id, sut_type, sut_version, sut_env
                FROM test_sessions
                ORDER BY sut_id, sut_version
                """
            )
            return [
                {
                    "sut_id": row[0],
                    "sut_type": row[1],
                    "version": row[2],
                    "environment": row[3],
                }
                for row in cursor.fetchall()
            ]

    def get_sut_stats(
        self,
        sut_id: Optional[str] = None,
        sut_type: Optional[str] = None,
        version: Optional[str] = None,
        environment: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[SutStats]:
        """Get statistics for SUTs matching the given criteria."""
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    ts.sut_id,
                    ts.sut_type,
                    ts.sut_version,
                    ts.sut_env,
                    COUNT(DISTINCT ts.id) as total_sessions,
                    SUM(ts.num_tests) as total_tests,
                    SUM(ts.num_passes) as total_passes,
                    SUM(ts.num_failures) as total_failures,
                    SUM(ts.num_reruns) as total_reruns,
                    MIN(ts.start_time) as first_seen,
                    MAX(ts.start_time) as last_seen
                FROM test_sessions ts
                WHERE 1=1
            """
            params = []

            if sut_id:
                query += " AND ts.sut_id = ?"
                params.append(sut_id)
            if sut_type:
                query += " AND ts.sut_type = ?"
                params.append(sut_type)
            if version:
                query += " AND ts.sut_version = ?"
                params.append(version)
            if environment:
                query += " AND ts.sut_env = ?"
                params.append(environment)
            if start_time:
                query += " AND ts.start_time >= ?"
                params.append(start_time)
            if end_time:
                query += " AND ts.start_time <= ?"
                params.append(end_time)

            query += """
                GROUP BY
                    ts.sut_id,
                    ts.sut_type,
                    ts.sut_version,
                    ts.sut_env
                ORDER BY
                    ts.sut_id,
                    ts.sut_version
            """

            cursor.execute(query, params)
            stats = []
            for row in cursor.fetchall():
                # Get flaky tests for this SUT
                cursor.execute(
                    """
                    SELECT DISTINCT tr.nodeid
                    FROM test_results tr
                    JOIN test_sessions ts ON tr.session_id = ts.id
                    WHERE ts.sut_id = ?
                        AND ts.sut_type = ?
                        AND ts.sut_version = ?
                        AND ts.sut_env = ?
                        AND tr.rerun_count > 0
                    """,
                    (row[0], row[1], row[2], row[3]),
                )
                flaky_tests = [r[0] for r in cursor.fetchall()]

                stats.append(
                    SutStats(
                        sut_id=row[0],
                        sut_type=row[1],
                        sut_version=row[2],
                        environment=row[3],
                        total_sessions=row[4],
                        total_tests=row[5],
                        total_passes=row[6],
                        total_failures=row[7],
                        total_reruns=row[8],
                        first_seen=row[9],
                        last_seen=row[10],
                        flaky_tests=flaky_tests,
                    )
                )

            return stats

    def analyze_test_trends(
        self,
        nodeid: Optional[str] = None,
        sut_id: Optional[str] = None,
        min_runs: int = 5,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[TestTrend]:
        """Analyze trends for tests matching the given criteria."""
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                WITH test_stats AS (
                    SELECT
                        tr.nodeid,
                        COUNT(*) as total_runs,
                        SUM(CASE WHEN tr.outcome = 'PASSED' THEN 1 ELSE 0 END) as passes,
                        SUM(CASE WHEN tr.outcome = 'FAILED' THEN 1 ELSE 0 END) as failures,
                        AVG(CAST(tr.rerun_count as FLOAT)) as avg_reruns,
                        MIN(tr.start_time) as first_seen,
                        MAX(tr.start_time) as last_seen
                    FROM test_results tr
                    JOIN test_sessions ts ON tr.session_id = ts.id
                    WHERE 1=1
            """
            params = []

            if nodeid:
                query += " AND tr.nodeid LIKE ?"
                params.append(f"%{nodeid}%")
            if sut_id:
                query += " AND ts.sut_id = ?"
                params.append(sut_id)
            if start_time:
                query += " AND tr.start_time >= ?"
                params.append(start_time)
            if end_time:
                query += " AND tr.start_time <= ?"
                params.append(end_time)

            query += """
                    GROUP BY tr.nodeid
                    HAVING COUNT(*) >= ?
                )
                SELECT
                    ts.nodeid,
                    ts.total_runs,
                    CAST(ts.passes as FLOAT) / ts.total_runs as pass_rate,
                    CAST(ts.failures as FLOAT) / ts.total_runs as failure_rate,
                    ts.avg_reruns,
                    ts.first_seen,
                    ts.last_seen
                FROM test_stats ts
                ORDER BY ts.total_runs DESC
            """
            params.append(min_runs)

            cursor.execute(query, params)
            trends = []
            for row in cursor.fetchall():
                nodeid = row[0]

                # Get environments and versions this test was run in
                cursor.execute(
                    """
                    SELECT DISTINCT ts.sut_env, ts.sut_version
                    FROM test_results tr
                    JOIN test_sessions ts ON tr.session_id = ts.id
                    WHERE tr.nodeid = ?
                    """,
                    (nodeid,),
                )
                envs_vers = cursor.fetchall()

                trends.append(
                    TestTrend(
                        nodeid=nodeid,
                        total_runs=row[1],
                        pass_rate=row[2],
                        failure_rate=row[3],
                        avg_reruns=row[4],
                        first_seen=row[5],
                        last_seen=row[6],
                        environments={ev[0] for ev in envs_vers},
                        sut_versions={ev[1] for ev in envs_vers},
                    )
                )

            return trends

    def get_flaky_tests(
        self,
        min_reruns: int = 1,
        sut_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Tuple[str, int, float]]:
        """Get a list of flaky tests ordered by number of reruns."""
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    tr.nodeid,
                    COUNT(*) as total_runs,
                    AVG(CAST(tr.rerun_count as FLOAT)) as avg_reruns
                FROM test_results tr
                JOIN test_sessions ts ON tr.session_id = ts.id
                WHERE tr.rerun_count > 0
            """
            params = []

            if sut_id:
                query += " AND ts.sut_id = ?"
                params.append(sut_id)
            if start_time:
                query += " AND tr.start_time >= ?"
                params.append(start_time)
            if end_time:
                query += " AND tr.start_time <= ?"
                params.append(end_time)

            query += """
                GROUP BY tr.nodeid
                HAVING SUM(tr.rerun_count) >= ?
                ORDER BY avg_reruns DESC, total_runs DESC
            """
            params.append(min_reruns)

            cursor.execute(query, params)
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def get_recently_failed_tests(
        self,
        hours: int = 24,
        min_failures: int = 1,
        sut_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Get tests that have failed recently.

        Args:
            hours: Look back period in hours
            min_failures: Minimum number of failures to include
            sut_id: Optional SUT ID to filter by

        Returns:
            Dict mapping test_id to failure details
        """
        return get_recent_failures(
            db_path=self.db_path, hours=hours, min_failures=min_failures, sut_id=sut_id
        )

    def get_duration_trends(
        self,
        days: int = 7,
        min_runs: int = 5,
        sut_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze test execution time trends.

        Args:
            days: Analysis period in days
            min_runs: Minimum runs to include in analysis
            sut_id: Optional SUT ID to filter by

        Returns:
            Dict mapping test_id to duration statistics
        """
        return get_duration_trends(
            db_path=self.db_path, days=days, min_runs=min_runs, sut_id=sut_id
        )

    def get_stability_report(
        self,
        days: int = 30,
        sut_id: Optional[str] = None,
        granularity: str = "day",
        verbose: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Generate test stability report over time.

        Args:
            days: Analysis period in days
            sut_id: Optional SUT ID to filter by
            granularity: Time grouping ('hour', 'day', 'week')
            verbose: If True, include full test details in output

        Returns:
            Dict with stability metrics over time
        """
        metrics = get_stability_metrics(
            db_path=self.db_path, days=days, sut_id=sut_id, granularity=granularity
        )

        if not verbose:
            # Remove detailed test information while keeping summary stats
            for period in metrics.get("flaky_tests", []):
                if len(period.get("tests", [])) > 3:
                    period["tests"] = period["tests"][:3] + ["..."]

        return metrics

    def get_error_patterns(
        self,
        days: int = 30,
        min_occurrences: int = 2,
        sut_id: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze error patterns in test failures.

        Args:
            days: Analysis period in days
            min_occurrences: Minimum occurrences of an error pattern to include
            sut_id: Optional SUT ID to filter by

        Returns:
            Dict with error patterns and their frequency
        """
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    tr.error_type,
                    tr.error_message,
                    COUNT(*) as occurrence_count,
                    GROUP_CONCAT(DISTINCT tr.test_id) as affected_tests,
                    MIN(tr.start_time) as first_seen,
                    MAX(tr.start_time) as last_seen
                FROM test_results tr
                JOIN test_sessions ts ON tr.session_id = ts.id
                WHERE tr.error_type IS NOT NULL
                AND tr.start_time >= datetime('now', ?)
            """
            params = [f"-{days} days"]

            if sut_id:
                query += " AND ts.sut_id = ?"
                params.append(sut_id)

            query += """
                GROUP BY tr.error_type, tr.error_message
                HAVING COUNT(*) >= ?
                ORDER BY occurrence_count DESC, last_seen DESC
            """
            params.append(min_occurrences)

            cursor.execute(query, params)
            patterns = []
            for row in cursor.fetchall():
                patterns.append(
                    {
                        "error_type": row[0],
                        "error_message": row[1],
                        "occurrence_count": row[2],
                        "affected_tests": row[3].split(",") if row[3] else [],
                        "first_seen": row[4],
                        "last_seen": row[5],
                    }
                )

            return {"error_patterns": patterns}

    def get_test_reliability(
        self,
        days: int = 30,
        min_runs: int = 5,
        sut_id: Optional[str] = None,
        reliability_threshold: float = 0.95,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze test reliability based on pass rates and execution patterns.

        Args:
            days: Analysis period in days
            min_runs: Minimum runs required for analysis
            sut_id: Optional SUT ID to filter by
            reliability_threshold: Threshold for considering a test reliable

        Returns:
            Dict with reliability metrics for tests
        """
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                WITH test_stats AS (
                    SELECT
                        tr.test_id,
                        COUNT(*) as total_runs,
                        SUM(CASE WHEN tr.outcome = 'passed' THEN 1 ELSE 0 END) as passes,
                        AVG(CASE WHEN tr.outcome = 'passed' THEN tr.duration ELSE NULL END) as avg_pass_duration,
                        AVG(tr.duration) as avg_duration,
                        MIN(tr.duration) as min_duration,
                        MAX(tr.duration) as max_duration,
                        SUM(CASE WHEN tr.rerun_count > 0 THEN 1 ELSE 0 END) as rerun_count,
                        AVG(CASE WHEN tr.rerun_count > 0 THEN tr.rerun_count ELSE 0 END) as avg_reruns_when_needed,
                        COUNT(DISTINCT tr.error_type) as unique_error_types,
                        MAX(tr.start_time) as last_run,
                        MAX(CASE WHEN tr.outcome = 'passed' THEN tr.start_time ELSE NULL END) as last_pass,
                        SUM(CASE WHEN tr.outcome = 'failed' THEN 1 ELSE 0 END) as failures,
                        SUM(CASE WHEN tr.outcome = 'skipped' THEN 1 ELSE 0 END) as skips,
                        SUM(CASE WHEN tr.outcome = 'xfailed' THEN 1 ELSE 0 END) as xfails,
                        SUM(CASE WHEN tr.outcome = 'xpassed' THEN 1 ELSE 0 END) as xpasses
                    FROM test_results tr
                    JOIN test_sessions ts ON tr.session_id = ts.id
                    WHERE tr.start_time >= datetime('now', ?)
                    """
            params = [f"-{days} days"]

            if sut_id:
                query += " AND ts.sut_id = ?"
                params.append(sut_id)

            query += """
                    GROUP BY tr.test_id
                    HAVING total_runs >= ?
                )
                SELECT
                    test_id,
                    total_runs,
                    CAST(passes as FLOAT) / total_runs as pass_rate,
                    avg_pass_duration,
                    avg_duration,
                    min_duration,
                    max_duration,
                    rerun_count,
                    avg_reruns_when_needed,
                    unique_error_types,
                    last_run,
                    last_pass,
                    failures,
                    skips,
                    xfails,
                    xpasses,
                    CASE
                        WHEN (CAST(passes as FLOAT) / total_runs) >= ?
                        AND rerun_count = 0
                        AND unique_error_types <= 1
                        THEN 1
                        ELSE 0
                    END as is_reliable
                FROM test_stats
                ORDER BY pass_rate DESC, total_runs DESC
            """
            params.extend([min_runs, reliability_threshold])

            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "test_id": row[0],
                        "total_runs": row[1],
                        "pass_rate": row[2],
                        "avg_pass_duration": row[3],
                        "avg_duration": row[4],
                        "min_duration": row[5],
                        "max_duration": row[6],
                        "rerun_count": row[7],
                        "avg_reruns_when_needed": row[8],
                        "unique_error_types": row[9],
                        "last_run": row[10],
                        "last_pass": row[11],
                        "failures": row[12],
                        "skips": row[13],
                        "xfails": row[14],
                        "xpasses": row[15],
                        "is_reliable": bool(row[16]),
                    }
                )

            return {
                "reliability_metrics": results,
                "summary": {
                    "total_tests": len(results),
                    "reliable_tests": sum(1 for r in results if r["is_reliable"]),
                    "unreliable_tests": sum(1 for r in results if not r["is_reliable"]),
                    "avg_pass_rate": sum(r["pass_rate"] for r in results) / len(results)
                    if results
                    else 0,
                },
            }
