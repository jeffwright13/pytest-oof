"""Analyzer interface for pytest-oof test data."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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
        self.db_path = db_path

    def get_all_suts(self) -> List[Dict[str, str]]:
        """Get a list of all unique SUTs in the database."""
        with db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT sut_id, sut_type, sut_version, sut_environment
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
                    ts.sut_environment,
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
                query += " AND ts.sut_environment = ?"
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
                    ts.sut_environment
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
                        AND ts.sut_environment = ?
                        AND tr.rerun_count > 0
                    """,
                    (row[0], row[1], row[2], row[3])
                )
                flaky_tests = [r[0] for r in cursor.fetchall()]
                
                stats.append(SutStats(
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
                    flaky_tests=flaky_tests
                ))
            
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
                    SELECT DISTINCT ts.sut_environment, ts.sut_version
                    FROM test_results tr
                    JOIN test_sessions ts ON tr.session_id = ts.id
                    WHERE tr.nodeid = ?
                    """,
                    (nodeid,)
                )
                envs_vers = cursor.fetchall()
                
                trends.append(TestTrend(
                    nodeid=nodeid,
                    total_runs=row[1],
                    pass_rate=row[2],
                    failure_rate=row[3],
                    avg_reruns=row[4],
                    first_seen=row[5],
                    last_seen=row[6],
                    environments={ev[0] for ev in envs_vers},
                    sut_versions={ev[1] for ev in envs_vers}
                ))
            
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
