"""Database operations for pytest-oof."""
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional, Union, Dict, Any, List
import sqlite3
from sqlite3 import Connection
import json
import sys

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker

from pytest_oof.models import (
    Base,
    SQLTestResult,
    SQLTestSession,
    TestResult,
    TestSession,
    TestSessionStats
)


class DBClient:
    """Database client for pytest-oof."""

    def __init__(self, session: Session):
        """Initialize database client."""
        self.session = session

    def add_session(self, session_data: Union[TestSession, Dict[str, Any]]) -> None:
        """Add test session to database."""
        try:
            if isinstance(session_data, TestSession):
                db_session = SQLTestSession(
                    session_id=session_data.session_id,
                    sut_id=session_data.sut_id,
                    start_time=session_data.start_time,
                    end_time=session_data.end_time,
                    duration=int(session_data.duration.total_seconds()) if session_data.duration else None,
                    total_tests=session_data.total_tests,
                    passed_tests=session_data.passed_tests,
                    failed_tests=session_data.failed_tests,
                    skipped_tests=session_data.skipped_tests,
                    xfailed_tests=session_data.xfailed_tests,
                    xpassed_tests=session_data.xpassed_tests,
                    warnings=session_data.warnings,
                    errors=session_data.errors,
                    rerun=session_data.rerun
                )
            else:
                db_session = SQLTestSession(
                    session_id=session_data['session_id'],
                    sut_id=session_data['sut_id'],
                    start_time=session_data.get('start_time'),
                    end_time=session_data.get('end_time'),
                    duration=int(session_data.get('duration', timedelta(0)).total_seconds()) if session_data.get('duration') else None,
                    total_tests=session_data.get('total_tests', 0),
                    passed_tests=session_data.get('passed_tests', 0),
                    failed_tests=session_data.get('failed_tests', 0),
                    skipped_tests=session_data.get('skipped_tests', 0),
                    xfailed_tests=session_data.get('xfailed_tests', 0),
                    xpassed_tests=session_data.get('xpassed_tests', 0),
                    warnings=session_data.get('warnings', 0),
                    errors=session_data.get('errors', 0),
                    rerun=session_data.get('rerun', 0)
                )

            self.session.add(db_session)
            self.session.commit()

        except Exception as e:
            print(f"Error adding session to database: {e}", file=sys.stderr)
            self.session.rollback()
            raise

    def add_test_result(self, result: TestResult, session_id: str):
        """Add a test result to the database.
        
        Args:
            result: TestResult object containing test result data
            session_id: ID of the test session
        """
        try:
            result_dict = result.to_dict()
            result_dict['session_id'] = session_id

            db_result = SQLTestResult(
                session_id=session_id,
                test_id=result.test_id,
                outcome=result.outcome,
                duration=result.duration,
                error_data=result_dict.get('error_data'),
                warnings=result.warnings,
                environment=result.environment,
                rerun_count=result.rerun_count
            )

            self.session.add(db_result)
            self.session.commit()
            return db_result
        except Exception as e:
            self.session.rollback()
            print(f"Error adding test result: {e}", file=sys.stderr)
            raise e

    def get_test_results(self, session_id=None):
        query = self.session.query(SQLTestResult)
        if session_id:
            query = query.filter(SQLTestResult.session_id == session_id)
        return query.all()

    def update_test_result(self, test_id, update_data):
        result = self.session.query(SQLTestResult).filter(
            SQLTestResult.test_id == test_id
        ).first()
        if result:
            for key, value in update_data.items():
                setattr(result, key, value)
            self.session.commit()
            return True
        return False

    def delete_test_result(self, test_id):
        result = self.session.query(SQLTestResult).filter(
            SQLTestResult.test_id == test_id
        ).first()
        if result:
            self.session.delete(result)
            self.session.commit()
            return True
        return False

    def update_session_stats(self, session_id: str, stats: TestSessionStats):
        """Update session statistics in the database.
        
        Args:
            session_id: The ID of the session to update
            stats: TestSessionStats object containing the statistics
        """
        try:
            session = self.session.query(SQLTestSession).filter(
                SQLTestSession.session_id == session_id
            ).first()
            
            if session:
                stats_dict = stats.to_dict()
                for key, value in stats_dict.items():
                    if hasattr(session, key):
                        if key == 'duration' and isinstance(value, timedelta):
                            value = int(value.total_seconds())
                        setattr(session, key, value)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error updating session stats: {e}", file=sys.stderr)
            raise e

def init_db(db_path: str = "oof/oof-results.db") -> Session:
    """Initialize the database."""
    connection_string = f"sqlite:///{db_path}"
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

@contextmanager
def db_connection(db_path: Path) -> Iterator[Connection]:
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_sqlite_db(db_path: Path) -> None:
    """Initialize the SQLite database with required tables."""
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Create sessions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                sut_id TEXT NOT NULL,
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
                rerun INTEGER DEFAULT 0
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
                duration INTEGER,
                error_data JSON,
                warnings JSON,
                rerun_count INTEGER DEFAULT 0,
                environment JSON,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            """
        )


def add_session(
    db_path: Path,
    start_time: datetime,
    session_id: str,
    sut_id: str,
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
                id,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                start_time,
                num_tests,
                num_tests_without_rerun,
                num_tests_total,
                num_passes,
                num_failures,
                num_errors,
                num_skips,
                num_xfails,
                num_xpasses,
                num_reruns,
                num_rerun_groups,
                num_warnings,
                num_warnings_unique,
                num_deselected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                start_time,
                0,  # num_tests
                0,  # num_tests_without_rerun
                0,  # num_tests_total
                0,  # num_passes
                0,  # num_failures
                0,  # num_errors
                0,  # num_skips
                0,  # num_xfails
                0,  # num_xpasses
                0,  # num_reruns
                0,  # num_rerun_groups
                0,  # num_warnings
                0,  # num_warnings_unique
                0,  # num_deselected
            ),
        )
        conn.commit()
        return session_id


def add_test_result(
    db_path: Path,
    session_id: str,
    test_result: Union[Dict[str, Any], TestResult],
) -> None:
    """Add a test result to the database."""
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Convert TestResult to dict if needed
        if isinstance(test_result, TestResult):
            test_result = test_result.to_dict()

        cursor.execute(
            """
            INSERT INTO test_results (
                session_id, nodeid, outcome, start_time, duration,
                error_message, error_type, error_traceback,
                has_warning, longreprtext, caplog, capstdout, capstderr,
                rerun_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                test_result["nodeid"],
                test_result["outcome"],
                test_result["start_time"],
                test_result["duration"],
                test_result["error_message"],
                test_result["error_type"],
                test_result["error_traceback"],
                test_result["has_warning"],
                test_result["longreprtext"],
                test_result["caplog"],
                test_result["capstdout"],
                test_result["capstderr"],
                test_result["rerun_count"],
            ),
        )
        conn.commit()  # Make sure changes are committed


def add_rerun_group(
    db_path: Path,
    session_id: str,
    group_name: str,
) -> None:
    """Add a rerun group to the database."""
    with db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO rerun_groups (session_id, group_name)
            VALUES (?, ?)
            """,
            (session_id, group_name),
        )


def update_session_stats(
    db_path: Path,
    session_id: str,
    stats: Union[Dict[str, Any], TestSessionStats],
    rerun_groups: List[str],
) -> None:
    """Update session statistics in the database."""
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Convert TestSessionStats to dict if needed
        if isinstance(stats, TestSessionStats):
            stats = stats.to_dict()

        print(f"Updating session stats for {session_id}: {stats}")  # Debug

        cursor.execute(
            """
            UPDATE test_sessions SET
                num_tests = ?,
                num_tests_without_rerun = ?,
                num_tests_total = ?,
                num_passes = ?,
                num_failures = ?,
                num_errors = ?,
                num_skips = ?,
                num_xfails = ?,
                num_xpasses = ?,
                num_reruns = ?,
                num_rerun_groups = ?,
                num_warnings = ?,
                num_warnings_unique = ?,
                num_deselected = ?
            WHERE id = ?
            """,
            (
                stats["num_tests"],
                stats["num_tests_without_rerun"],
                stats["num_tests_total"],
                stats["num_passes"],
                stats["num_failures"],
                stats["num_errors"],
                stats["num_skips"],
                stats["num_xfails"],
                stats["num_xpasses"],
                stats["num_reruns"],
                stats["num_rerun_groups"],
                stats["num_warnings"],
                stats["num_warnings_unique"],
                stats["num_deselected"],
                session_id,
            ),
        )
        conn.commit()  # Make sure changes are committed

        # Verify the update
        cursor.execute(
            """
            SELECT
                num_tests,
                num_tests_without_rerun,
                num_tests_total,
                num_passes,
                num_failures,
                num_reruns,
                num_rerun_groups
            FROM test_sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        print(f"After update: {row}")  # Debug

        # Update rerun groups
        cursor.execute("DELETE FROM rerun_groups WHERE session_id = ?", (session_id,))
        for group in rerun_groups:
            cursor.execute(
                "INSERT INTO rerun_groups (session_id, group_name) VALUES (?, ?)",
                (session_id, group),
            )
        conn.commit()  # Make sure changes are committed


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

        # Build query conditions for sessions
        query = """
            SELECT
                ts.session_id,
                ts.sut_id,
                ts.start_time,
                ts.end_time,
                ts.duration,
                ts.total_tests,
                ts.passed_tests,
                ts.failed_tests,
                ts.skipped_tests,
                ts.xfailed_tests,
                ts.xpassed_tests,
                ts.warnings,
                ts.errors,
                ts.rerun
            FROM sessions ts
            WHERE 1=1
        """
        params = []

        if start_time:
            query += " AND ts.start_time >= ?"
            params.append(start_time)
        if end_time:
            query += " AND ts.end_time <= ?"
            params.append(end_time)
        if last_n_sessions:
            query += " ORDER BY ts.start_time DESC LIMIT ?"
            params.append(last_n_sessions)

        # Get sessions
        print(f"Executing query: {query} with params: {params}")  # Debug
        c.execute(query, params)
        sessions = []
        for row in c.fetchall():
            print(f"Raw row: {row}")  # Debug
            session_dict = {
                "session": {
                    "id": row[0],  # Use single ID field
                    "timing": {"start": row[2], "stop": row[3], "duration": row[4]},
                    "sut": {
                        "id": row[1],
                        "type": "",  # These fields no longer exist in schema
                        "version": "",
                        "environment": "",
                        "metadata": None,
                    },
                    "statistics": {
                        "tests": {
                            "total": row[5],
                            "without_rerun": 0,  # These fields no longer exist
                            "with_rerun": 0,
                        },
                        "outcomes": {
                            "passed": row[6],
                            "failed": row[7],
                            "error": row[12],
                            "skipped": row[8],
                            "xfailed": row[9],
                            "xpassed": row[10],
                        },
                        "reruns": {"total": row[13], "groups": []},  # These fields no longer exist
                        "warnings": {"total": row[11], "unique": 0},
                        "deselected": 0,
                    },
                },
                "test_results": [],
            }
            print(f"Session stats: {session_dict['session']['statistics']}")  # Debug

            # Get test results for this session
            test_results_query = """
                SELECT
                    test_id,
                    outcome,
                    timestamp,
                    duration,
                    error_data,
                    warnings,
                    rerun_count,
                    environment
                FROM test_results
                WHERE session_id = ?
                ORDER BY timestamp
            """
            c.execute(test_results_query, [session[0]])
            test_results = c.fetchall()

            # Organize test results by outcome for easier analysis
            results_by_outcome = {}
            for tr in test_results:
                outcome = tr[1].lower()
                if outcome not in results_by_outcome:
                    results_by_outcome[outcome] = []

                result = {
                    "id": tr[0],  # test_id
                    "timing": {"start": tr[2], "duration": tr[3]},
                }

                # Only include error info if present
                error_data = json.loads(tr[4]) if tr[4] else None
                if error_data:
                    result["error"] = error_data

                # Include warnings if present
                warnings = json.loads(tr[5]) if tr[5] else None
                if warnings:
                    result["warnings"] = warnings

                # Include environment if present
                env = json.loads(tr[7]) if tr[7] else None
                if env:
                    result["environment"] = env

                # Include rerun count if present
                if tr[6]:  # rerun_count
                    result["rerun_count"] = tr[6]

                results_by_outcome[outcome].append(result)

            session_dict["test_results"] = results_by_outcome
            sessions.append(session_dict)

        return sessions


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
            FROM sessions s
        """

        # Add join with test_results if filtering by outcome or test_id
        if outcome is not None or test_id is not None:
            query += " LEFT JOIN test_results r ON s.session_id = r.session_id"
        query += " WHERE 1=1"
        params = []

        # Add filters
        if session_id is not None:
            query += " AND s.session_id = ?"
            params.append(session_id)
        if start_time is not None:
            query += " AND s.start_time >= ?"
            params.append(start_time)
        if end_time is not None:
            query += " AND s.start_time <= ?"
            params.append(end_time)
        if sut_id is not None and sut_id != "":
            query += " AND s.sut_id = ?"
            params.append(sut_id)
        if sut_type is not None and sut_type != "":
            query += " AND s.sut_type = ?"
            params.append(sut_type)
        if sut_version is not None and sut_version != "":
            query += " AND s.sut_version = ?"
            params.append(sut_version)
        if sut_env is not None and sut_env != "":
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
                    error_data,
                    warnings,
                    rerun_count,
                    environment
                FROM test_results
                WHERE session_id = ?
                ORDER BY timestamp
            """
            c.execute(test_results_query, [session[0]])
            test_results = c.fetchall()

            # Convert to dictionary with a more organized structure
            session_dict = {
                "session": {
                    "id": session[0],  # Use single ID field
                    "timing": {
                        "start": session[2],
                        "stop": session[3],
                        "duration": session[4],
                    },
                    "sut": {
                        "id": session[1],
                        "type": "",  # These fields no longer exist in schema
                        "version": "",
                        "environment": "",
                        "metadata": None,
                    },
                    "statistics": {
                        "tests": {
                            "total": session[5],
                            "without_rerun": 0,  # These fields no longer exist
                            "with_rerun": 0,
                        },
                        "outcomes": {
                            "passed": session[6],
                            "failed": session[7],
                            "error": session[12],
                            "skipped": session[8],
                            "xfailed": session[9],
                            "xpassed": session[10],
                        },
                        "reruns": {"total": session[13], "groups": []},  # These fields no longer exist
                        "warnings": {"total": session[11], "unique": 0},
                        "deselected": 0,
                    },
                },
                "test_results": [],
            }

            # Organize test results by outcome for easier analysis
            results_by_outcome = {}
            for tr in test_results:
                outcome = tr[1].lower()
                if outcome not in results_by_outcome:
                    results_by_outcome[outcome] = []

                result = {
                    "id": tr[0],  # test_id
                    "timing": {"start": tr[2], "duration": tr[3]},
                }

                # Only include error info if present
                error_data = json.loads(tr[4]) if tr[4] else None
                if error_data:
                    result["error"] = error_data

                # Include warnings if present
                warnings = json.loads(tr[5]) if tr[5] else None
                if warnings:
                    result["warnings"] = warnings

                # Include environment if present
                env = json.loads(tr[7]) if tr[7] else None
                if env:
                    result["environment"] = env

                # Include rerun count if present
                if tr[6]:  # rerun_count
                    result["rerun_count"] = tr[6]

                results_by_outcome[outcome].append(result)

            session_dict["test_results"] = results_by_outcome
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
        where_clauses = []
        params = []

        if all_results:
            # Delete all test results first
            cursor.execute("DELETE FROM test_results")
            # Then delete all sessions
            cursor.execute("DELETE FROM sessions")
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

        # Build WHERE clause for filtering sessions
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

        # Handle last_n_sessions
        session_ids = []
        if last_n_sessions:
            cursor.execute(
                """
                SELECT session_id FROM sessions
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (last_n_sessions,),
            )
            session_ids = [row[0] for row in cursor.fetchall()]
            if session_ids:
                where_clauses.append(f"session_id IN ({','.join('?' * len(session_ids))})")
                params.extend(session_ids)

        # Build base query for getting session IDs to delete
        query = "SELECT session_id FROM sessions"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Get the session IDs that will be deleted
        cursor.execute(query, params)
        session_ids_to_delete = [row[0] for row in cursor.fetchall()]

        if session_ids_to_delete:
            # Delete test results for these sessions first
            cursor.execute(
                f"DELETE FROM test_results WHERE session_id IN ({','.join('?' * len(session_ids_to_delete))})",
                session_ids_to_delete,
            )

            # Then delete the sessions
            cursor.execute(
                f"DELETE FROM sessions WHERE session_id IN ({','.join('?' * len(session_ids_to_delete))})",
                session_ids_to_delete,
            )
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

        return 0


def get_db_id_from_session_id(db_path: Path, session_id: str) -> Optional[int]:
    """Get the database ID for a session given its session_id."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT session_id FROM sessions WHERE session_id = ?
            """,
            (session_id,),
        )
        row = c.fetchone()
        return row[0] if row else None
