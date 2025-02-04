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
    with db_connection(db_path) as conn:
        c = conn.cursor()

        # Check if schema version table exists
        c.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_version';
            """
        )
        schema_version_exists = c.fetchone() is not None

        if schema_version_exists:
            # Check current schema version
            c.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            current_version = row[0] if row else 0
        else:
            current_version = 0

        # Drop all tables if schema version is outdated
        if current_version < 4:  # Current schema version
            c.executescript(
                """
                DROP TABLE IF EXISTS test_sessions;
                DROP TABLE IF EXISTS console_output;
                DROP TABLE IF EXISTS report_metrics;
                DROP TABLE IF EXISTS test_results;
                DROP TABLE IF EXISTS fixtures;
                DROP TABLE IF EXISTS test_fixture_usage;
                DROP TABLE IF EXISTS resource_metrics;
                DROP TABLE IF EXISTS test_artifacts;
                DROP TABLE IF EXISTS system_state;
                DROP TABLE IF EXISTS schema_version;

                -- Create schema version table and set version
                CREATE TABLE schema_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO schema_version (version, created_at)
                VALUES (4, CURRENT_TIMESTAMP);

                -- Test sessions table to store metadata about each test run
                CREATE TABLE test_sessions (
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
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_test_sessions_sut_id ON test_sessions(sut_id);
                CREATE INDEX idx_test_sessions_sut_type ON test_sessions(sut_type);
                CREATE INDEX idx_test_sessions_start_time ON test_sessions(start_time);

                -- Test results table to store individual test outcomes
                CREATE TABLE test_results (
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
                CREATE INDEX idx_test_results_session_id ON test_results(session_id);
                CREATE INDEX idx_test_results_test_id ON test_results(test_id);
                CREATE INDEX idx_test_results_outcome ON test_results(outcome);
                CREATE INDEX idx_test_results_timestamp ON test_results(timestamp);

                -- Console output table to store stdout/stderr lines
                CREATE TABLE console_output (
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
                CREATE INDEX idx_console_output_session_id ON console_output(session_id);
                CREATE INDEX idx_console_output_timestamp ON console_output(timestamp);
                CREATE INDEX idx_console_output_line_number ON console_output(line_number);

                -- Report metrics table to store report-based statistics
                CREATE TABLE report_metrics (
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
                CREATE INDEX idx_report_metrics_session_id ON report_metrics(session_id);
                CREATE INDEX idx_report_metrics_metric_type ON report_metrics(metric_type);
                CREATE INDEX idx_report_metrics_timestamp ON report_metrics(timestamp);

                -- Resource metrics table to store resource usage metrics
                CREATE TABLE resource_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX idx_resource_metrics_session_id ON resource_metrics(session_id);
                CREATE INDEX idx_resource_metrics_metric_type ON resource_metrics(metric_type);
                CREATE INDEX idx_resource_metrics_timestamp ON resource_metrics(timestamp);

                -- Test artifacts table to store test-related files
                CREATE TABLE test_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    test_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX idx_test_artifacts_session_id ON test_artifacts(session_id);
                CREATE INDEX idx_test_artifacts_test_id ON test_artifacts(test_id);

                -- System state table to store system information
                CREATE TABLE system_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    state_type TEXT NOT NULL,
                    state_value TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX idx_system_state_session_id ON system_state(session_id);
                CREATE INDEX idx_system_state_state_type ON system_state(state_type);
                CREATE INDEX idx_system_state_timestamp ON system_state(timestamp);

                -- Fixtures table to store fixture information
                CREATE TABLE fixtures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    fixture_id TEXT NOT NULL,
                    fixture_type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX idx_fixtures_session_id ON fixtures(session_id);
                CREATE INDEX idx_fixtures_fixture_id ON fixtures(fixture_id);

                -- Test fixture usage table to store test-fixture relationships
                CREATE TABLE test_fixture_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    test_id TEXT NOT NULL,
                    fixture_id INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES test_sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (fixture_id) REFERENCES fixtures(id) ON DELETE CASCADE
                );
                CREATE INDEX idx_test_fixture_usage_session_id ON test_fixture_usage(session_id);
                CREATE INDEX idx_test_fixture_usage_test_id ON test_fixture_usage(test_id);
                CREATE INDEX idx_test_fixture_usage_fixture_id ON test_fixture_usage(fixture_id);
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
                sut_env
            ) VALUES (?, ?, ?, ?, ?)
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
                outcome,
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
            params.append(outcome)
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
                params.append(outcome)
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
                    "num_tests": session[8],
                    "num_passes": session[9],
                    "num_failures": session[10],
                    "num_errors": session[11],
                    "num_skips": session[12],
                    "num_xfails": session[13],
                    "num_xpasses": session[14],
                    "num_reruns": session[15],
                    "num_rerun_groups": session[16],
                    "num_warnings": session[17],
                    "num_warnings_unique": session[18],
                    "num_deselected": session[19],
                },
                "test_results": [
                    {
                        "test_id": tr[0],
                        "outcome": tr[1],
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
                json.dump(results, f, indent=2, default=str)

        return results
