"""Database operations for pytest-oof."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


def init_db(db_path: Path) -> None:
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tables with indices for faster querying
    c.executescript(
        """
        -- Test sessions table to store metadata about each test run
        CREATE TABLE IF NOT EXISTS test_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            sut_id TEXT,
            sut_type TEXT,
            sut_version TEXT,
            sut_env TEXT,
            python_version TEXT,
            os_info TEXT,
            pytest_version TEXT,
            command_line TEXT,
            report_based BOOLEAN DEFAULT 0,  -- Flag to indicate if this session uses report-based stats
            UNIQUE(start_time, sut_id, sut_type, sut_version, sut_env)
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_time ON test_sessions(start_time);

        -- Console output table for report-based analysis
        CREATE TABLE IF NOT EXISTS console_output (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            line_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            line_type TEXT,  -- header, summary, test_result, error, warning, etc.
            parsed_data TEXT,  -- JSON string of any structured data parsed from this line
            FOREIGN KEY(session_id) REFERENCES test_sessions(id)
        );
        CREATE INDEX IF NOT EXISTS idx_console_session ON console_output(session_id);
        CREATE INDEX IF NOT EXISTS idx_console_type ON console_output(line_type);

        -- Report-based metrics table
        CREATE TABLE IF NOT EXISTS report_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            metric_type TEXT NOT NULL,  -- collected, selected, deselected, passed, failed, etc.
            metric_value INTEGER NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            source_line_id INTEGER,  -- Reference to console line where this was parsed from
            FOREIGN KEY(session_id) REFERENCES test_sessions(id),
            FOREIGN KEY(source_line_id) REFERENCES console_output(id)
        );
        CREATE INDEX IF NOT EXISTS idx_report_metrics_type ON report_metrics(metric_type);
        CREATE INDEX IF NOT EXISTS idx_report_metrics_session ON report_metrics(session_id);

        -- Test results table to store individual test outcomes
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            test_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            duration REAL,
            error_message TEXT,
            error_type TEXT,
            error_traceback TEXT,
            parameters TEXT,  -- JSON string of test parameters
            source_line_id INTEGER,  -- NULL for plugin-based, set for report-based
            FOREIGN KEY(session_id) REFERENCES test_sessions(id),
            FOREIGN KEY(source_line_id) REFERENCES console_output(id),
            UNIQUE(session_id, test_id, timestamp)
        );
        CREATE INDEX IF NOT EXISTS idx_results_test ON test_results(test_id);
        CREATE INDEX IF NOT EXISTS idx_results_time ON test_results(timestamp);

        -- Fixtures table to track fixture usage and timing
        CREATE TABLE IF NOT EXISTS fixtures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            scope TEXT NOT NULL,  -- session, package, module, class, function
            timestamp TIMESTAMP NOT NULL,
            setup_duration REAL,
            teardown_duration REAL,
            error_message TEXT,
            error_type TEXT,
            error_traceback TEXT,
            FOREIGN KEY(session_id) REFERENCES test_sessions(id)
        );
        CREATE INDEX IF NOT EXISTS idx_fixtures_name ON fixtures(name);
        CREATE INDEX IF NOT EXISTS idx_fixtures_session ON fixtures(session_id);

        -- Test-Fixture relationships
        CREATE TABLE IF NOT EXISTS test_fixture_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_result_id INTEGER NOT NULL,
            fixture_id INTEGER NOT NULL,
            FOREIGN KEY(test_result_id) REFERENCES test_results(id),
            FOREIGN KEY(fixture_id) REFERENCES fixtures(id),
            UNIQUE(test_result_id, fixture_id)
        );

        -- Resource metrics table (Level 3)
        CREATE TABLE IF NOT EXISTS resource_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            test_result_id INTEGER,  -- NULL for session-wide metrics
            fixture_id INTEGER,      -- NULL for test or session metrics
            timestamp TIMESTAMP NOT NULL,
            metric_type TEXT NOT NULL,  -- cpu, memory, disk, network, etc.
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metric_unit TEXT,
            FOREIGN KEY(session_id) REFERENCES test_sessions(id),
            FOREIGN KEY(test_result_id) REFERENCES test_results(id),
            FOREIGN KEY(fixture_id) REFERENCES fixtures(id)
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_type ON resource_metrics(metric_type);
        CREATE INDEX IF NOT EXISTS idx_metrics_time ON resource_metrics(timestamp);

        -- Test artifacts table (Level 3)
        CREATE TABLE IF NOT EXISTS test_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_result_id INTEGER NOT NULL,
            artifact_type TEXT NOT NULL,  -- log, screenshot, dump, etc.
            artifact_path TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            metadata TEXT,  -- JSON string of additional metadata
            FOREIGN KEY(test_result_id) REFERENCES test_results(id)
        );
        CREATE INDEX IF NOT EXISTS idx_artifacts_type ON test_artifacts(artifact_type);

        -- System state snapshots (Level 3)
        CREATE TABLE IF NOT EXISTS system_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            test_result_id INTEGER,  -- NULL for session-wide state
            timestamp TIMESTAMP NOT NULL,
            state_type TEXT NOT NULL,  -- env_vars, loaded_modules, open_files, etc.
            state_data TEXT NOT NULL,  -- JSON string of state information
            FOREIGN KEY(session_id) REFERENCES test_sessions(id),
            FOREIGN KEY(test_result_id) REFERENCES test_results(id)
        );
        CREATE INDEX IF NOT EXISTS idx_state_type ON system_state(state_type);
        CREATE INDEX IF NOT EXISTS idx_state_time ON system_state(timestamp);
    """
    )

    conn.commit()
    conn.close()


def add_session(
    db_path: Path,
    start_time: datetime,
    sut_id: str = "",
    sut_type: str = "",
    sut_version: str = "",
    sut_env: str = "",
) -> int:
    """Add a new test session and return its ID."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO test_sessions (start_time, sut_id, sut_type, sut_version, sut_env)
        VALUES (?, ?, ?, ?, ?)
    """,
        (start_time, sut_id, sut_type, sut_version, sut_env),
    )

    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def add_test_result(
    db_path: Path,
    session_id: int,
    test_id: str,
    outcome: str,
    timestamp: datetime,
    duration: Optional[float] = None,
) -> None:
    """Add a test result to the database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO test_results (session_id, test_id, outcome, timestamp, duration)
        VALUES (?, ?, ?, ?, ?)
    """,
        (session_id, test_id, outcome, timestamp, duration),
    )

    conn.commit()
    conn.close()


def get_test_results(
    db_path: Path,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    test_id: Optional[str] = None,
    last_n_sessions: Optional[int] = None,
) -> list:
    """Query test results with optional filters."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

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
    conn.close()

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
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO console_output
        (session_id, timestamp, line_number, content, line_type, parsed_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (session_id, timestamp, line_number, content, line_type, parsed_data),
    )

    line_id = c.lastrowid
    conn.commit()
    conn.close()
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
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO report_metrics
        (session_id, metric_type, metric_value, timestamp, source_line_id)
        VALUES (?, ?, ?, ?, ?)
    """,
        (session_id, metric_type, metric_value, timestamp, source_line_id),
    )

    conn.commit()
    conn.close()
