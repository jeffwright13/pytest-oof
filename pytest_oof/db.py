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

        # Create test_sessions table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                duration REAL,
                sut_id TEXT,
                sut_type TEXT,
                sut_version TEXT,
                sut_env TEXT,
                sut_metadata TEXT,
                python_version TEXT,
                os_info TEXT,
                pytest_version TEXT,
                command_line TEXT,
                report_based BOOLEAN DEFAULT 1,
                num_tests INTEGER DEFAULT 0,
                num_passes INTEGER DEFAULT 0,
                num_failures INTEGER DEFAULT 0,
                num_errors INTEGER DEFAULT 0,
                num_skips INTEGER DEFAULT 0,
                num_xfails INTEGER DEFAULT 0,
                num_xpasses INTEGER DEFAULT 0,
                num_reruns INTEGER DEFAULT 0,
                num_rerun_groups INTEGER DEFAULT 0,
                num_warnings INTEGER DEFAULT 0,
                num_deselected INTEGER DEFAULT 0
            )
            """
        )

        # Create test_results table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                test_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                duration REAL,
                error_message TEXT,
                error_type TEXT,
                error_traceback TEXT,
                has_warning BOOLEAN DEFAULT 0,
                longreprtext TEXT,
                FOREIGN KEY (session_id) REFERENCES test_sessions (id)
            )
            """
        )

        # Create schema version table and set version
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Check current schema version
        c.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        current_version = row[0] if row else 0

        # Update schema version if needed
        if current_version < 6:  # Increment version for longreprtext column
            c.execute(
                """
                INSERT INTO schema_version (version) VALUES (?)
                """,
                (6,),
            )

        # Commit all changes
        conn.commit()


def add_session(
    db_path: Path,
    start_time: datetime,
    session_id: str,
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
                session_id,
                start_time,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                report_based,
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
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """,
            (
                session_id,
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
    has_warning: bool = False,
    longreprtext: Optional[str] = None,
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
                has_warning,
                longreprtext
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                has_warning,
                longreprtext,
            ),
        )

        result_id = c.lastrowid
        conn.commit()

        return result_id


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
                    has_warning,
                    longreprtext
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

            # Convert to dictionary
            session_dict = {
                "session": {
                    "id": session[0],  # database id
                    "session_id": session[1],  # uuid
                    "start_time": session[2],
                    "end_time": session[3],
                    "duration": session[4],
                    "sut_id": session[5],
                    "sut_type": session[6],
                    "sut_version": session[7],
                    "sut_env": session[8],
                    "sut_metadata": json.loads(session[9]) if session[9] else None,
                    "python_version": session[10],
                    "os_info": session[11],
                    "pytest_version": session[12],
                    "command_line": session[13],
                    "report_based": bool(session[14]),
                    "num_tests": session[15],
                    "num_passes": session[16],
                    "num_failures": session[17],
                    "num_errors": session[18],
                    "num_skips": session[19],
                    "num_xfails": session[20],
                    "num_xpasses": session[21],
                    "num_reruns": session[22],
                    "num_rerun_groups": session[23],
                    "num_warnings": session[24],
                    "num_deselected": session[25],
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
                        "has_warning": tr[7],
                        "longreprtext": tr[8],
                        "session_id": session[0],
                    }
                    for tr in test_results
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
            SELECT outcome, has_warning
            FROM test_results
            WHERE session_id = ?
            """,
            (session_id,),
        )
        test_results = c.fetchall()

        # Calculate stats
        num_tests = len(test_results)
        num_passes = sum(1 for (outcome, _) in test_results if outcome == "PASSED")
        num_failures = sum(1 for (outcome, _) in test_results if outcome == "FAILED")
        num_skips = sum(1 for (outcome, _) in test_results if outcome == "SKIPPED")
        num_errors = sum(1 for (outcome, _) in test_results if outcome == "ERROR")
        num_xfails = sum(1 for (outcome, _) in test_results if outcome == "XFAIL")
        num_xpasses = sum(1 for (outcome, _) in test_results if outcome == "XPASS")
        num_reruns = sum(1 for (outcome, _) in test_results if outcome == "RERUN")
        num_warnings = sum(1 for (_, has_warning) in test_results if has_warning)

        # Get unique test IDs to calculate rerun groups
        c.execute(
            """
            SELECT test_id, COUNT(*) as run_count
            FROM test_results
            WHERE session_id = ?
            GROUP BY test_id
            HAVING run_count > 1
            """,
            (session_id,),
        )
        rerun_groups = c.fetchall()
        num_rerun_groups = len(rerun_groups)

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
                num_xpasses = ?,
                num_reruns = ?,
                num_rerun_groups = ?,
                num_warnings = ?
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
                num_reruns,
                num_rerun_groups,
                num_warnings,
                session_id,
            ),
        )
        conn.commit()


def get_db_id_from_session_id(db_path: Path, session_id: str) -> Optional[int]:
    """Get the database ID for a session given its session_id."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT id FROM test_sessions WHERE session_id = ?
            """,
            (session_id,),
        )
        row = c.fetchone()
        return row[0] if row else None
