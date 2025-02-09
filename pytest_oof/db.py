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
                db_session = TestSession(
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
                db_session = TestSession(
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

            db_result = TestResult(
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
        query = self.session.query(TestResult)
        if session_id:
            query = query.filter(TestResult.session_id == session_id)
        return query.all()

    def update_test_result(self, test_id, update_data):
        result = self.session.query(TestResult).filter(
            TestResult.test_id == test_id
        ).first()
        if result:
            for key, value in update_data.items():
                setattr(result, key, value)
            self.session.commit()
            return True
        return False

    def delete_test_result(self, test_id):
        result = self.session.query(TestResult).filter(
            TestResult.test_id == test_id
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
            session = self.session.query(TestSession).filter(
                TestSession.session_id == session_id
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
                rerun INTEGER DEFAULT 0
            )
            """
        )

        # Create test_results table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                test_id TEXT NOT NULL,
                outcome TEXT,
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
                rerun_count INTEGER,
                environment TEXT,
                warnings TEXT,
                is_rerun BOOLEAN,
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
) -> str:
    """Add a new test session to the database and return its ID."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO sessions (
                session_id,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                start_time,
                total_tests,
                passed_tests,
                failed_tests,
                skipped_tests,
                xfailed_tests,
                xpassed_tests,
                warnings,
                errors,
                rerun
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                start_time,
                0,  # total_tests
                0,  # passed_tests
                0,  # failed_tests
                0,  # skipped_tests
                0,  # xfailed_tests
                0,  # xpassed_tests
                0,  # warnings
                0,  # errors
                0,  # rerun
            ),
        )
        conn.commit()
        return session_id


def add_test_result(
    db_path: Path,
    session_id: str,
    test_id: str,
    outcome: str,
    duration: float = 0.0,
    error_data: Optional[Dict[str, Any]] = None,
    environment: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    rerun_count: int = 0,
    timestamp: Optional[datetime] = None,
) -> None:
    """Add a test result to the database."""
    with db_connection(db_path) as conn:
        c = conn.cursor()

        result = TestResult(
            test_id=test_id,
            outcome=outcome,
            duration=duration,
            error_data=error_data,
            environment=environment,
            warnings=warnings,
            rerun_count=rerun_count,
            session_id=session_id,
        )

        if timestamp:
            result.timestamp = timestamp

        c.execute(
            """
            INSERT INTO test_results (
                session_id,
                test_id,
                outcome,
                duration,
                error_data,
                warnings,
                environment,
                rerun_count,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                test_id,
                outcome,
                duration,
                json.dumps(error_data) if error_data else None,
                json.dumps(warnings) if warnings else "[]",
                json.dumps(environment) if environment else "{}",
                rerun_count,
                timestamp or datetime.now(),
            ),
        )
        conn.commit()


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
            UPDATE sessions SET
                total_tests = ?,
                passed_tests = ?,
                failed_tests = ?,
                skipped_tests = ?,
                xfailed_tests = ?,
                xpassed_tests = ?,
                warnings = ?,
                errors = ?,
                rerun = ?
            WHERE session_id = ?
            """,
            (
                stats["total_tests"],
                stats["passed_tests"],
                stats["failed_tests"],
                stats["skipped_tests"],
                stats["xfailed_tests"],
                stats["xpassed_tests"],
                stats["warnings"],
                stats["errors"],
                stats["rerun"],
                session_id,
            ),
        )
        conn.commit()  # Make sure changes are committed

        # Verify the update
        cursor.execute(
            """
            SELECT
                total_tests,
                passed_tests,
                failed_tests,
                skipped_tests,
                xfailed_tests,
                xpassed_tests,
                warnings,
                errors,
                rerun
            FROM sessions
            WHERE session_id = ?
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
                    start_time,
                    duration,
                    error_message,
                    error_type,
                    error_traceback,
                    has_warning,
                    longreprtext,
                    caplog,
                    capstdout,
                    capstderr,
                    rerun_count,
                    environment,
                    warnings,
                    is_rerun
                FROM test_results
                WHERE session_id = ?
                ORDER BY start_time
            """
            c.execute(test_results_query, [session[0]])
            test_results = c.fetchall()

            # Convert to dictionary with a more organized structure
            session_dict = {
                "session": {
                    "id": session[0],  # session_id
                    "timing": {
                        "start": session[2],  # start_time
                        "stop": session[3],   # end_time
                        "duration": session[4],  # duration
                    },
                    "sut": {
                        "id": session[1],  # sut_id
                        "type": session[5],  # sut_type
                        "version": session[6],  # sut_version
                        "environment": session[7],  # sut_env
                    },
                    "statistics": {
                        "tests": {
                            "total": session[8],  # total_tests
                        },
                        "outcomes": {
                            "passed": session[9],  # passed_tests
                            "failed": session[10],  # failed_tests
                            "skipped": session[11],  # skipped_tests
                            "xfailed": session[12],  # xfailed_tests
                            "xpassed": session[13],  # xpassed_tests
                        },
                        "warnings": {"total": session[14]},  # warnings
                        "errors": {"total": session[15]},  # errors
                        "reruns": {"total": session[16]},  # rerun
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
                    "timing": {"start": tr[2], "duration": tr[3]},  # start_time, duration
                }

                # Add error info if present
                if tr[4] or tr[5] or tr[6]:  # error_message, error_type, error_traceback
                    result["error"] = {
                        "message": tr[4],
                        "type": tr[5],
                        "traceback": tr[6]
                    }

                # Add longreprtext if present
                if tr[8]:  # longreprtext
                    result["longrepr"] = tr[8]

                # Add capture output if present
                capture = {}
                if tr[9]:  # caplog
                    capture["log"] = tr[9]
                if tr[10]:  # capstdout
                    capture["out"] = tr[10]
                if tr[11]:  # capstderr
                    capture["err"] = tr[11]
                if capture:
                    result["capture"] = capture

                # Add rerun info if present
                if tr[12]:  # rerun_count
                    result["rerun_count"] = tr[12]
                if tr[15]:  # is_rerun
                    result["is_rerun"] = tr[15]

                # Add environment if present
                if tr[13]:  # environment
                    result["environment"] = json.loads(tr[13])

                # Add warnings if present
                if tr[14]:  # warnings
                    result["warnings"] = json.loads(tr[14])

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
            SELECT DISTINCT
                s.session_id,
                s.sut_id,
                s.start_time,
                s.end_time,
                s.duration,
                s.total_tests,
                s.passed_tests,
                s.failed_tests,
                s.skipped_tests,
                s.xfailed_tests,
                s.xpassed_tests,
                s.warnings,
                s.errors,
                s.rerun
            FROM sessions s
            INNER JOIN test_results r ON s.session_id = r.session_id
            WHERE 1=1
        """

        # Add filters
        params = []
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
                    start_time,
                    duration,
                    error_message,
                    error_type,
                    error_traceback,
                    has_warning,
                    longreprtext,
                    caplog,
                    capstdout,
                    capstderr,
                    rerun_count,
                    environment,
                    warnings,
                    is_rerun
                FROM test_results
                WHERE session_id = ?
                ORDER BY start_time
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
                    "timing": {"start": tr[2], "duration": tr[3]},  # start_time, duration
                }

                # Add error info if present
                if tr[4] or tr[5] or tr[6]:  # error_message, error_type, error_traceback
                    result["error"] = {
                        "message": tr[4],
                        "type": tr[5],
                        "traceback": tr[6]
                    }

                # Add longreprtext if present
                if tr[8]:  # longreprtext
                    result["longrepr"] = tr[8]

                # Add capture output if present
                capture = {}
                if tr[9]:  # caplog
                    capture["log"] = tr[9]
                if tr[10]:  # capstdout
                    capture["out"] = tr[10]
                if tr[11]:  # capstderr
                    capture["err"] = tr[11]
                if capture:
                    result["capture"] = capture

                # Add rerun info if present
                if tr[12]:  # rerun_count
                    result["rerun_count"] = tr[12]
                if tr[15]:  # is_rerun
                    result["is_rerun"] = tr[15]

                # Add environment if present
                if tr[13]:  # environment
                    result["environment"] = json.loads(tr[13])

                # Add warnings if present
                if tr[14]:  # warnings
                    result["warnings"] = json.loads(tr[14])

                results_by_outcome[outcome].append(result)

            session_dict["test_results"] = results_by_outcome
            results.append(session_dict)

        if output_file:
            with open(output_file, "w") as f:
                if output_format == "jsonl":
                    if not results:
                        f.write("")  # Write empty file for no results
                    else:
                        for result in results:
                            f.write(json.dumps(result, default=str) + "\n")
                else:  # json
                    if not results:
                        f.write("[]")  # Write empty array for no results
                    else:
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


def get_recent_failures(
    db_path: Path,
    hours: int = 24,
    min_failures: int = 1,
    sut_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Get tests that have failed recently.
    
    Args:
        db_path: Path to the SQLite database file
        hours: Look back period in hours
        min_failures: Minimum number of failures to include
        sut_id: Optional SUT ID to filter by
        
    Returns:
        Dict mapping test_id to failure details
    """
    since = datetime.now() - timedelta(hours=hours)
    results = get_test_results(
        db_path=db_path,
        start_time=since,
        outcome='failed'
    )
    
    failed_tests = {}
    for result in results:
        test_id = result['test_id']
        if test_id not in failed_tests:
            failed_tests[test_id] = {
                'last_failure': result['timestamp'],
                'failure_count': 1,
                'error_messages': [result['error_data']['message']] if result['error_data'] else [],
                'environments': [result['environment']] if result['environment'] else []
            }
        else:
            failed_tests[test_id]['failure_count'] += 1
            if result['error_data']:
                failed_tests[test_id]['error_messages'].append(result['error_data']['message'])
            if result['environment']:
                failed_tests[test_id]['environments'].append(result['environment'])
            if result['timestamp'] > failed_tests[test_id]['last_failure']:
                failed_tests[test_id]['last_failure'] = result['timestamp']
    
    return {
        test_id: data 
        for test_id, data in failed_tests.items() 
        if data['failure_count'] >= min_failures
    }


def get_duration_trends(
    db_path: Path,
    days: int = 7,
    min_runs: int = 5,
    sut_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Analyze test execution time trends.
    
    Args:
        db_path: Path to the SQLite database file
        days: Analysis period in days
        min_runs: Minimum runs to include in analysis
        sut_id: Optional SUT ID to filter by
        
    Returns:
        Dict mapping test_id to duration statistics
    """
    since = datetime.now() - timedelta(days=days)
    results = get_test_results(
        db_path=db_path,
        start_time=since
    )
    
    duration_data = {}
    for result in results:
        if result['outcome'] not in ('passed', 'failed'):
            continue
            
        test_id = result['test_id']
        if test_id not in duration_data:
            duration_data[test_id] = {
                'durations': [(result['duration'], result['timestamp'])],
                'run_count': 1
            }
        else:
            duration_data[test_id]['durations'].append((result['duration'], result['timestamp']))
            duration_data[test_id]['run_count'] += 1
    
    trends = {}
    for test_id, data in duration_data.items():
        if data['run_count'] < min_runs:
            continue
            
        durations = [d[0] for d in data['durations']]
        timestamps = [d[1] for d in data['durations']]
        
        # Calculate trend using linear regression
        x = [(t - min(timestamps)).total_seconds() / 86400 for t in timestamps]  # Convert to days
        y = durations
        n = len(x)
        if n < 2:
            continue
            
        slope = (n * sum(x[i] * y[i] for i in range(n)) - sum(x) * sum(y)) / \
               (n * sum(x[i] * x[i] for i in range(n)) - sum(x) * sum(x))
        
        trends[test_id] = {
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'trend': slope,  # seconds/day
            'run_count': data['run_count']
        }
        
    return trends


def get_stability_metrics(
    db_path: Path,
    days: int = 30,
    sut_id: Optional[str] = None,
    granularity: str = 'day'
) -> Dict[str, List[Dict[str, Any]]]:
    """Generate test stability metrics over time.
    
    Args:
        db_path: Path to the SQLite database file
        days: Analysis period in days
        sut_id: Optional SUT ID to filter by
        granularity: Time grouping ('hour', 'day', 'week')
        
    Returns:
        Dict with stability metrics over time
    """
    since = datetime.now() - timedelta(days=days)
    results = get_test_results(
        db_path=db_path,
        start_time=since
    )
    
    # Group results by time period
    periods = {}
    for result in results:
        timestamp = result['timestamp']
        if granularity == 'hour':
            period = timestamp.replace(minute=0, second=0, microsecond=0)
        elif granularity == 'day':
            period = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # week
            period = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            period -= timedelta(days=period.weekday())
            
        if period not in periods:
            periods[period] = []
        periods[period].append(result)
    
    stability_report = {
        'stability_score': [],
        'failure_rate': [],
        'flaky_tests': []
    }
    
    for period, period_results in sorted(periods.items()):
        total_tests = len(period_results)
        if total_tests == 0:
            continue
            
        failed = len([r for r in period_results if r['outcome'] == 'failed'])
        
        # Identify flaky tests (tests that both passed and failed in this period)
        test_outcomes = {}
        for r in period_results:
            if r['test_id'] not in test_outcomes:
                test_outcomes[r['test_id']] = set()
            test_outcomes[r['test_id']].add(r['outcome'])
        
        flaky = {
            test_id 
            for test_id, outcomes in test_outcomes.items() 
            if 'passed' in outcomes and 'failed' in outcomes
        }
        
        stability_report['stability_score'].append({
            'period': period,
            'score': 1.0 - (failed / total_tests) - (len(flaky) / total_tests * 0.5)
        })
        
        stability_report['failure_rate'].append({
            'period': period,
            'rate': failed / total_tests
        })
        
        stability_report['flaky_tests'].append({
            'period': period,
            'count': len(flaky),
            'tests': list(flaky)
        })
        
    return stability_report
