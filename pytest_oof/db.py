"""Database operations for pytest-oof."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@contextmanager
def db_connection(db_path: Path):
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    try:
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """Initialize the SQLite database with required tables."""
    # Create parent directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with db_connection(db_path) as conn:
        c = conn.cursor()

        # Create tables if they don't exist
        c.executescript(
            """
            -- Create schema version table and set version
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            -- Test sessions table to store metadata about each test run
            CREATE TABLE IF NOT EXISTS test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration REAL,  -- Duration in seconds
                sut_id TEXT,
                sut_type TEXT,
                sut_version TEXT,
                sut_env TEXT,
                python_version TEXT,
                os_info TEXT,
                pytest_version TEXT,
                command_line TEXT,
                report_based BOOLEAN DEFAULT 0,  -- Flag to indicate if this session uses report-based stats
                num_tests INTEGER,
                num_passes INTEGER,
                num_failures INTEGER,
                num_errors INTEGER,
                num_skips INTEGER,
                num_xfails INTEGER,
                num_xpasses INTEGER,
                num_reruns INTEGER,
                num_rerun_groups INTEGER,
                num_warnings INTEGER,
                num_deselected INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_test_sessions_sut_id ON test_sessions(sut_id);
            CREATE INDEX IF NOT EXISTS idx_test_sessions_sut_type ON test_sessions(sut_type);
            CREATE INDEX IF NOT EXISTS idx_test_sessions_start_time ON test_sessions(start_time);

            -- Test results table to store individual test outcomes
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                test_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                duration REAL,  -- Duration in seconds
                error_message TEXT,
                error_type TEXT,
                error_traceback TEXT,
                parameters TEXT,  -- JSON string of test parameters
                source_line_id INTEGER,
                has_warning BOOLEAN DEFAULT 0,
                caplog TEXT,
                capstderr TEXT,
                capstdout TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (source_line_id) REFERENCES console_output(id) ON DELETE SET NULL,
                UNIQUE (session_id, test_id, timestamp)
            );
            CREATE INDEX IF NOT EXISTS idx_test_results_session_id ON test_results(session_id);
            CREATE INDEX IF NOT EXISTS idx_test_results_test_id ON test_results(test_id);
            CREATE INDEX IF NOT EXISTS idx_test_results_outcome ON test_results(outcome);
            CREATE INDEX IF NOT EXISTS idx_test_results_timestamp ON test_results(timestamp);

            -- Console output table to store stdout/stderr lines
            CREATE TABLE IF NOT EXISTS console_output (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                line_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                line_type TEXT,  -- Type of line (e.g., stdout, stderr, log)
                parsed_data TEXT,  -- JSON string of parsed data
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_console_output_session_id ON console_output(session_id);
            CREATE INDEX IF NOT EXISTS idx_console_output_timestamp ON console_output(timestamp);
            CREATE INDEX IF NOT EXISTS idx_console_output_line_number ON console_output(line_number);

            -- Report metrics table to store report-based statistics
            CREATE TABLE IF NOT EXISTS report_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                metric_type TEXT NOT NULL,
                metric_value INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                source_line_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (source_line_id) REFERENCES console_output(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_report_metrics_session_id ON report_metrics(session_id);
            CREATE INDEX IF NOT EXISTS idx_report_metrics_metric_type ON report_metrics(metric_type);
            CREATE INDEX IF NOT EXISTS idx_report_metrics_timestamp ON report_metrics(timestamp);

            -- Resource metrics table to store resource usage metrics
            CREATE TABLE IF NOT EXISTS resource_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                metric_type TEXT NOT NULL,
                metric_value REAL NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_resource_metrics_session_id ON resource_metrics(session_id);
            CREATE INDEX IF NOT EXISTS idx_resource_metrics_metric_type ON resource_metrics(metric_type);
            CREATE INDEX IF NOT EXISTS idx_resource_metrics_timestamp ON resource_metrics(timestamp);

            -- Test artifacts table to store test-related files
            CREATE TABLE IF NOT EXISTS test_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                test_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_test_artifacts_session_id ON test_artifacts(session_id);
            CREATE INDEX IF NOT EXISTS idx_test_artifacts_test_id ON test_artifacts(test_id);

            -- System state table to store system information
            CREATE TABLE IF NOT EXISTS system_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                state_type TEXT NOT NULL,
                state_value TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_system_state_session_id ON system_state(session_id);
            CREATE INDEX IF NOT EXISTS idx_system_state_state_type ON system_state(state_type);
            CREATE INDEX IF NOT EXISTS idx_system_state_timestamp ON system_state(timestamp);

            -- Fixtures table to store fixture information
            CREATE TABLE IF NOT EXISTS fixtures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                fixture_id TEXT NOT NULL,
                fixture_type TEXT NOT NULL,
                scope TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_fixtures_session_id ON fixtures(session_id);
            CREATE INDEX IF NOT EXISTS idx_fixtures_fixture_id ON fixtures(fixture_id);

            -- Test fixture usage table to store test-fixture relationships
            CREATE TABLE IF NOT EXISTS test_fixture_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                test_id TEXT NOT NULL,
                fixture_id INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (fixture_id) REFERENCES fixtures(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_test_fixture_usage_session_id ON test_fixture_usage(session_id);
            CREATE INDEX IF NOT EXISTS idx_test_fixture_usage_test_id ON test_fixture_usage(test_id);
            CREATE INDEX IF NOT EXISTS idx_test_fixture_usage_fixture_id ON test_fixture_usage(fixture_id);
            """
        )

        # Check current schema version
        c.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        current_version = row[0] if row else 0

        # Update schema version if needed
        if current_version < 4:  # Current schema version
            c.execute(
                """
                INSERT INTO schema_version (version, created_at)
                VALUES (4, CURRENT_TIMESTAMP)
                """
            )
            conn.commit()


def add_session(
    db_path: Path,
    start_time: datetime,
    sut_id: str = "",
    sut_type: str = "",
    sut_version: str = "",
    sut_env: str = "",
) -> int:
    """Add a new test session to the database and return its ID."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO test_sessions (
                start_time,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                num_tests,
                num_passes,
                num_failures,
                num_errors,
                num_skips,
                num_xfails,
                num_xpasses,
                num_reruns,
                num_rerun_groups,
                num_warnings,
                num_deselected
            ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """,
            (
                start_time,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
            ),
        )
        session_id = c.lastrowid
        conn.commit()
        return session_id


def add_test_result(
    db_path: Path,
    session_id: int,
    test_id: str,
    outcome: str,
    timestamp: datetime,
    duration: Optional[float] = None,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    error_traceback: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    source_line_id: Optional[int] = None,
    has_warning: bool = False,
    caplog: Optional[str] = None,
    capstderr: Optional[str] = None,
    capstdout: Optional[str] = None,
) -> int:
    """Add a test result to the database and return its ID."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO test_results (
                session_id,
                test_id,
                outcome,
                timestamp,
                duration,
                error_message,
                error_type,
                error_traceback,
                parameters,
                source_line_id,
                has_warning,
                caplog,
                capstderr,
                capstdout
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                test_id,
                outcome.upper(),  # Convert outcome to uppercase
                timestamp,
                duration,
                error_message,
                error_type,
                error_traceback,
                json.dumps(parameters) if parameters else None,
                source_line_id,
                has_warning,
                caplog,
                capstderr,
                capstdout,
            ),
        )
        test_result_id = c.lastrowid
        conn.commit()
        return test_result_id


def get_test_results(
    db_path: Path,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    test_id: Optional[str] = None,
    last_n_sessions: Optional[int] = None,
) -> list:
    """Query test results with optional filters."""
    with db_connection(db_path) as conn:
        c = conn.cursor()

        # Build query conditions
        query = """
            SELECT
                tr.test_id,
                tr.outcome,
                tr.timestamp,
                tr.duration,
                ts.sut_id,
                ts.sut_type,
                ts.sut_version,
                ts.sut_env
            FROM test_results tr
            JOIN test_sessions ts ON tr.session_id = ts.id
            WHERE 1=1
        """
        params = []

        if start_time:
            query += " AND tr.timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND tr.timestamp <= ?"
            params.append(end_time)
        if test_id:
            query += " AND tr.test_id = ?"
            params.append(test_id)
        if last_n_sessions:
            query = f"""
                WITH LastSessions AS (
                    SELECT id FROM test_sessions
                    ORDER BY start_time DESC
                    LIMIT {last_n_sessions}
                )
                {query}
                AND ts.id IN (SELECT id FROM LastSessions)
            """

        query += " ORDER BY tr.timestamp"

        c.execute(query, params)
        results = c.fetchall()
        return results


def add_console_line(
    db_path: Path,
    session_id: int,
    timestamp: datetime,
    line_number: int,
    content: str,
    line_type: Optional[str] = None,
    parsed_data: Optional[str] = None,
) -> int:
    """Add a console output line to the database."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO console_output (
                session_id, timestamp, line_number, content, line_type, parsed_data
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (session_id, timestamp, line_number, content, line_type, parsed_data),
        )

        line_id = c.lastrowid
        conn.commit()
        return line_id


def add_report_metric(
    db_path: Path,
    session_id: int,
    metric_type: str,
    metric_value: int,
    timestamp: datetime,
    source_line_id: Optional[int] = None,
) -> None:
    """Add a report-based metric to the database."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO report_metrics (
                session_id, metric_type, metric_value, timestamp, source_line_id
            )
            VALUES (?, ?, ?, ?, ?)
        """,
            (session_id, metric_type, metric_value, timestamp, source_line_id),
        )
        conn.commit()


def export_results(
    db_path: Path,
    session_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    sut_id: Optional[str] = None,
    sut_type: Optional[str] = None,
    sut_version: Optional[str] = None,
    sut_env: Optional[str] = None,
    output_file: Optional[Path] = None,
    output_format: str = "json",  # Can be "json" or "jsonl"
    outcome: Optional[str] = None,
    test_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Export test results from the database."""
    with db_connection(db_path) as conn:
        c = conn.cursor()

        # Build the base query for test sessions
        query = """
            SELECT DISTINCT s.*
            FROM test_sessions s
        """

        # Add join with test_results if filtering by outcome or test_id
        if outcome is not None or test_id is not None:
            query += " JOIN test_results r ON s.id = r.session_id"

        query += " WHERE 1=1"
        params = []

        # Add filters
        if session_id is not None:
            query += " AND s.id = ?"
            params.append(session_id)
        if start_time is not None:
            query += " AND s.start_time >= ?"
            params.append(start_time)
        if end_time is not None:
            query += " AND s.start_time <= ?"
            params.append(end_time)
        if sut_id is not None:
            query += " AND s.sut_id = ?"
            params.append(sut_id)
        if sut_type is not None:
            query += " AND s.sut_type = ?"
            params.append(sut_type)
        if sut_version is not None:
            query += " AND s.sut_version = ?"
            params.append(sut_version)
        if sut_env is not None:
            query += " AND s.sut_env = ?"
            params.append(sut_env)
        if outcome is not None:
            query += " AND r.outcome = ?"
            params.append(outcome.upper())  # Convert outcome filter to uppercase
        if test_id is not None:
            query += " AND r.test_id = ?"
            params.append(test_id)

        query += " ORDER BY s.start_time DESC"
        c.execute(query, params)
        sessions = c.fetchall()

        results = []
        for session in sessions:
            # Get test results for this session
            test_results_query = """
                SELECT
                    test_id,
                    outcome,
                    timestamp,
                    duration,
                    error_message,
                    error_type,
                    error_traceback,
                    parameters,
                    has_warning,
                    caplog,
                    capstderr,
                    capstdout
                FROM test_results
                WHERE session_id = ?
            """
            params = [session[0]]

            if outcome is not None:
                test_results_query += " AND outcome = ?"
                params.append(outcome.upper())  # Convert outcome filter to uppercase
            if test_id is not None:
                test_results_query += " AND test_id = ?"
                params.append(test_id)

            test_results_query += " ORDER BY timestamp"
            c.execute(test_results_query, params)
            test_results = c.fetchall()

            # Get metrics for this session
            c.execute(
                """
                SELECT metric_type, metric_value
                FROM report_metrics
                WHERE session_id = ?
                ORDER BY timestamp
                """,
                (session[0],),
            )
            metrics = c.fetchall()

            # Convert to dictionary
            session_dict = {
                "session": {
                    "session_id": session[0],
                    "start_time": session[1],
                    "end_time": session[2],
                    "duration": session[3],
                    "sut_id": session[4],
                    "sut_type": session[5],
                    "sut_version": session[6],
                    "sut_env": session[7],
                    "python_version": session[8],
                    "os_info": session[9],
                    "pytest_version": session[10],
                    "command_line": session[11],
                    "report_based": session[12],
                    "num_tests": session[13],
                    "num_passes": session[14],
                    "num_failures": session[15],
                    "num_errors": session[16],
                    "num_skips": session[17],
                    "num_xfails": session[18],
                    "num_xpasses": session[19],
                    "num_reruns": session[20],
                    "num_rerun_groups": session[21],
                    "num_warnings": session[22],
                    "num_deselected": session[23],
                },
                "test_results": [
                    {
                        "test_id": tr[0],
                        "outcome": tr[1].lower(),  # Convert outcome to lowercase
                        "timestamp": tr[2],
                        "duration": tr[3],
                        "error_message": tr[4],
                        "error_type": tr[5],
                        "error_traceback": tr[6],
                        "parameters": json.loads(tr[7]) if tr[7] else None,
                        "has_warning": tr[8],
                        "caplog": tr[9],
                        "capstderr": tr[10],
                        "capstdout": tr[11],
                        "session_id": session[0],
                    }
                    for tr in test_results
                ],
                "metrics": [
                    {
                        "type": m[0],
                        "value": m[1],
                    }
                    for m in metrics
                ],
            }
            results.append(session_dict)

        if output_file:
            with open(output_file, "w") as f:
                if output_format == "jsonl":
                    for result in results:
                        f.write(json.dumps(result, default=str) + "\n")
                else:  # json
                    json.dump(results, f, indent=2, default=str)

        return results


def delete_results(
    db_path: Path,
    *,
    all_results: bool = False,
    last_n_sessions: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    sut_id: Optional[str] = None,
    sut_type: Optional[str] = None,
) -> int:
    """Delete test results from the database based on specified criteria.

    Args:
        db_path: Path to the SQLite database file
        all_results: If True, delete all results (overrides other filters)
        last_n_sessions: Delete the last N sessions
        start_time: Delete sessions starting from this time
        end_time: Delete sessions up to this time
        sut_id: Delete sessions for this SUT ID
        sut_type: Delete sessions for this SUT type

    Returns:
        Number of sessions deleted
    """
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Build WHERE clause based on filters
        where_clauses = []
        params = []

        if not all_results:
            if start_time:
                where_clauses.append("start_time >= ?")
                params.append(start_time)
            if end_time:
                where_clauses.append("start_time <= ?")
                params.append(end_time)
            if sut_id:
                where_clauses.append("sut_id = ?")
                params.append(sut_id)
            if sut_type:
                where_clauses.append("sut_type = ?")
                params.append(sut_type)

        # For last N sessions, we need to get the session IDs first
        if last_n_sessions:
            cursor.execute(
                """
                SELECT id FROM test_sessions
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (last_n_sessions,),
            )
            session_ids = [row[0] for row in cursor.fetchall()]
            if session_ids:
                where_clauses.append(f"id IN ({','.join('?' * len(session_ids))})")
                params.extend(session_ids)

        # Build and execute the DELETE query
        query = "DELETE FROM test_sessions"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        cursor.execute(query, params)
        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count


def update_session_stats(db_path: Path, session_id: int) -> None:
    """Update session statistics based on test results."""
    with db_connection(db_path) as conn:
        c = conn.cursor()

        # Get all test results for this session
        c.execute(
            """
            SELECT outcome
            FROM test_results
            WHERE session_id = ?
            """,
            (session_id,),
        )
        test_results = c.fetchall()

        # Calculate stats
        num_tests = len(test_results)
        num_passes = sum(1 for (outcome,) in test_results if outcome == "PASSED")
        num_failures = sum(1 for (outcome,) in test_results if outcome == "FAILED")
        num_skips = sum(1 for (outcome,) in test_results if outcome == "SKIPPED")
        num_errors = sum(1 for (outcome,) in test_results if outcome == "ERROR")
        num_xfails = sum(1 for (outcome,) in test_results if outcome == "XFAIL")
        num_xpasses = sum(1 for (outcome,) in test_results if outcome == "XPASS")

        # Update session stats
        c.execute(
            """
            UPDATE test_sessions
            SET num_tests = ?,
                num_passes = ?,
                num_failures = ?,
                num_errors = ?,
                num_skips = ?,
                num_xfails = ?,
                num_xpasses = ?
            WHERE id = ?
            """,
            (
                num_tests,
                num_passes,
                num_failures,
                num_errors,
                num_skips,
                num_xfails,
                num_xpasses,
                session_id,
            ),
        )
        conn.commit()
