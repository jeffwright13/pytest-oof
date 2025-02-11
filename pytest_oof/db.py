"""Database operations for pytest-oof."""
import json
import sqlite3
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Dict, Iterator, List, Optional, Union

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker

from pytest_oof.models import Base, TestResult, TestSession, TestSessionStats


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
                    duration=int(session_data.duration.total_seconds())
                    if session_data.duration
                    else None,
                    total_tests=session_data.total_tests,
                    passed_tests=session_data.passed_tests,
                    failed_tests=session_data.failed_tests,
                    skipped_tests=session_data.skipped_tests,
                    xfailed_tests=session_data.xfailed_tests,
                    xpassed_tests=session_data.xpassed_tests,
                    warnings=session_data.warnings,
                    errors=session_data.errors,
                    rerun=session_data.rerun,
                )
            else:
                db_session = TestSession(
                    session_id=session_data["session_id"],
                    sut_id=session_data["sut_id"],
                    start_time=session_data.get("start_time"),
                    end_time=session_data.get("end_time"),
                    duration=int(
                        session_data.get("duration", timedelta(0)).total_seconds()
                    )
                    if session_data.get("duration")
                    else None,
                    total_tests=session_data.get("total_tests", 0),
                    passed_tests=session_data.get("passed_tests", 0),
                    failed_tests=session_data.get("failed_tests", 0),
                    skipped_tests=session_data.get("skipped_tests", 0),
                    xfailed_tests=session_data.get("xfailed_tests", 0),
                    xpassed_tests=session_data.get("xpassed_tests", 0),
                    warnings=session_data.get("warnings", 0),
                    errors=session_data.get("errors", 0),
                    rerun=session_data.get("rerun", 0),
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
            result_dict["session_id"] = session_id

            db_result = TestResult(
                session_id=session_id,
                test_id=result.test_id,
                outcome=result.outcome,
                duration=result.duration,
                error_data=result_dict.get("error_data"),
                environment=result.environment,
                warnings=result.warnings,
                rerun_count=result.rerun_count,
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
        result = (
            self.session.query(TestResult).filter(TestResult.test_id == test_id).first()
        )
        if result:
            for key, value in update_data.items():
                setattr(result, key, value)
            self.session.commit()
            return True
        return False

    def delete_test_result(self, test_id):
        result = (
            self.session.query(TestResult).filter(TestResult.test_id == test_id).first()
        )
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
            session = (
                self.session.query(TestSession)
                .filter(TestSession.session_id == session_id)
                .first()
            )

            if session:
                stats_dict = stats.to_dict()
                for key, value in stats_dict.items():
                    if hasattr(session, key):
                        if key == "duration" and isinstance(value, timedelta):
                            value = int(value.total_seconds())
                        setattr(session, key, value)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error updating session stats: {e}", file=sys.stderr)
            raise e


def init_db(db_path: str = "./.oof/oof-results.db") -> Session:
    """Initialize the database."""
    connection_string = f"sqlite:///{db_path}"
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def init_sqlite_db(db_path: Path) -> None:
    """Initialize the SQLite database with required tables."""
    db_path = Path(db_path)
    db_dir = db_path.parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
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
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            """
        )

        # Check if we need to add new columns
        cursor.execute("PRAGMA table_info(test_results)")
        columns = {col[1] for col in cursor.fetchall()}

        if "rerun_outcomes" not in columns:
            cursor.execute(
                "ALTER TABLE test_results ADD COLUMN rerun_outcomes TEXT DEFAULT '[]'"
            )

        cursor.execute("PRAGMA table_info(sessions)")
        columns = {col[1] for col in cursor.fetchall()}

        if "rerun_outcomes" not in columns:
            cursor.execute(
                "ALTER TABLE sessions ADD COLUMN rerun_outcomes TEXT DEFAULT '[]'"
            )

        if "rerun_recovery_rate" not in columns:
            cursor.execute(
                "ALTER TABLE sessions ADD COLUMN rerun_recovery_rate REAL DEFAULT 0.0"
            )

        if "rerun_total_time" not in columns:
            cursor.execute(
                "ALTER TABLE sessions ADD COLUMN rerun_total_time REAL DEFAULT 0.0"
            )

        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_connection(db_path: Path) -> Iterator[Connection]:
    """Context manager for database connections."""
    db_path = Path(db_path)
    db_dir = db_path.parent
    db_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database if it doesn't exist
    if not db_path.exists():
        init_sqlite_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


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
                rerun,
                rerun_outcomes,
                rerun_recovery_rate,
                rerun_total_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                start_time.isoformat(),  # Convert datetime to ISO format string
                0,  # total_tests
                0,  # passed_tests
                0,  # failed_tests
                0,  # skipped_tests
                0,  # xfailed_tests
                0,  # xpassed_tests
                0,  # warnings
                0,  # errors
                0,  # rerun
                "[]",  # rerun_outcomes
                0.0,  # rerun_recovery_rate
                0.0,  # rerun_total_time
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
    rerun_outcomes: Optional[List[str]] = None,
    timestamp: Optional[datetime] = None,
) -> None:
    """Add a test result to the database."""
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Parse error data
        error_message = None
        error_type = None
        error_traceback = None
        if error_data:
            error_message = error_data.get("message")
            error_type = error_data.get("type")
            error_traceback = error_data.get("traceback")

        # Convert environment to JSON string if present
        env_json = json.dumps(environment) if environment else None
        warnings_json = json.dumps(warnings) if warnings else None
        rerun_outcomes_json = json.dumps(rerun_outcomes) if rerun_outcomes else "[]"

        # Use current time if no timestamp provided
        if timestamp is None:
            timestamp = datetime.now()

        cursor.execute(
            """
            INSERT INTO test_results (
                session_id,
                test_id,
                outcome,
                start_time,
                duration,
                error_message,
                error_type,
                error_traceback,
                environment,
                warnings,
                rerun_count,
                rerun_outcomes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                env_json,
                warnings_json,
                rerun_count,
                rerun_outcomes_json,
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
                rerun = ?,
                end_time = ?,
                duration = ?,
                rerun_outcomes = ?,
                rerun_recovery_rate = ?,
                rerun_total_time = ?
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
                stats["end_time"].isoformat() if stats["end_time"] else None,
                int(stats["duration"].total_seconds()) if stats["duration"] else None,
                json.dumps(stats["rerun_outcomes"])
                if stats["rerun_outcomes"]
                else "[]",
                stats["rerun_recovery_rate"],
                stats["rerun_total_time"],
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
    outcome: Optional[str] = None,
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
                ts.rerun,
                tr.test_id,
                tr.outcome,
                tr.start_time as test_start_time,
                tr.duration as test_duration,
                tr.error_message,
                tr.error_type,
                tr.error_traceback,
                tr.has_warning,
                tr.longreprtext,
                tr.caplog,
                tr.capstdout,
                tr.capstderr,
                tr.rerun_count,
                tr.environment,
                tr.warnings as test_warnings,
                tr.is_rerun,
                tr.rerun_outcomes
            FROM sessions ts
            JOIN test_results tr ON ts.session_id = tr.session_id
            WHERE 1=1
        """
        params = []

        if start_time:
            query += " AND ts.start_time >= ?"
            params.append(start_time)
        if end_time:
            query += " AND ts.end_time <= ?"
            params.append(end_time)
        if test_id:
            query += " AND tr.test_id = ?"
            params.append(test_id)
        if outcome:
            query += " AND tr.outcome = ?"
            params.append(outcome)
        if last_n_sessions:
            query += " ORDER BY ts.start_time DESC LIMIT ?"
            params.append(last_n_sessions)

        # Get sessions
        print(f"Executing query: {query} with params: {params}")  # Debug
        c.execute(query, params)
        results = []
        for row in c.fetchall():
            print(f"Raw row: {row}")  # Debug
            test_result = {
                "session_id": row[0],
                "sut_id": row[1],
                "test_id": row[14],  # From the JOIN with test_results
                "outcome": row[15],
                "timestamp": datetime.fromisoformat(row[16])
                if isinstance(row[16], str)
                else row[16],  # test_start_time
                "duration": row[17],
                "error_data": {
                    "message": row[18],  # error_message
                    "type": row[19],  # error_type
                    "traceback": row[20],  # error_traceback
                }
                if row[18] or row[19] or row[20]
                else None,
                "has_warning": row[21],
                "longreprtext": row[22],
                "caplog": row[23],
                "capstdout": row[24],
                "capstderr": row[25],
                "rerun_count": row[26],
                "environment": row[27],
                "warnings": row[28],
                "is_rerun": row[29],
                "rerun_outcomes": json.loads(row[30]) if row[30] else [],
            }
            results.append(test_result)

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
                s.rerun,
                s.rerun_outcomes,
                s.rerun_recovery_rate,
                s.rerun_total_time,
                s.sut_type,
                s.sut_version,
                s.sut_env
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
                    is_rerun,
                    rerun_outcomes
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
                        "start": datetime.fromisoformat(session[2])
                        if isinstance(session[2], str)
                        else session[2],
                        "stop": datetime.fromisoformat(session[3])
                        if isinstance(session[3], str)
                        else session[3],
                        "duration": session[4],
                    },
                    "sut": {
                        "id": session[1],
                        "type": session[15] or "",  # sut_type
                        "version": session[16] or "",  # sut_version
                        "environment": session[17] or "",  # sut_env
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
                        "reruns": {
                            "total": session[13],
                            "outcomes": json.loads(session[14])
                            if session[14]
                            else [],  # rerun_outcomes
                            "groups": [],
                            "recovery_rate": session[18],
                            "total_time": session[19],
                        },
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
                    "timing": {
                        "start": datetime.fromisoformat(tr[2])
                        if isinstance(tr[2], str)
                        else tr[2],
                        "duration": tr[3],
                    },  # start_time, duration
                }

                # Add error info if present
                if (
                    tr[4] or tr[5] or tr[6]
                ):  # error_message, error_type, error_traceback
                    result["error"] = {
                        "message": tr[4],
                        "type": tr[5],
                        "traceback": tr[6],
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

                # Add rerun outcomes if present
                if tr[16]:  # rerun_outcomes
                    result["rerun_outcomes"] = json.loads(tr[16])

                results_by_outcome[outcome].append(result)

            session_dict["test_results"] = results_by_outcome
            results.append(session_dict)

        if output_file:
            # Write results to file
            with open(output_file, "w") as f:
                if output_format == "jsonl":
                    for result in results:
                        f.write(json.dumps(result, default=str) + "\n")
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
                where_clauses.append(
                    f"session_id IN ({','.join('?' * len(session_ids))})"
                )
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
    results = get_test_results(db_path=db_path, start_time=since, outcome="failed")

    failed_tests = {}
    for result in results:
        test_id = result["test_id"]
        if test_id not in failed_tests:
            failed_tests[test_id] = {
                "last_failure": result["timestamp"],
                "failure_count": 1,
                "error_messages": [result["error_data"]["message"]]
                if result["error_data"]
                else [],
                "environments": [result["environment"]]
                if result["environment"]
                else [],
            }
        else:
            failed_tests[test_id]["failure_count"] += 1
            if result["error_data"]:
                failed_tests[test_id]["error_messages"].append(
                    result["error_data"]["message"]
                )
            if result["environment"]:
                failed_tests[test_id]["environments"].append(result["environment"])
            if result["timestamp"] > failed_tests[test_id]["last_failure"]:
                failed_tests[test_id]["last_failure"] = result["timestamp"]

    return {
        test_id: data
        for test_id, data in failed_tests.items()
        if data["failure_count"] >= min_failures
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
    results = get_test_results(db_path=db_path, start_time=since)

    duration_data = {}
    for result in results:
        if result["outcome"] not in ("passed", "failed"):
            continue

        test_id = result["test_id"]
        timestamp = (
            datetime.fromisoformat(result["timestamp"])
            if isinstance(result["timestamp"], str)
            else result["timestamp"]
        )

        if test_id not in duration_data:
            duration_data[test_id] = {
                "durations": [(result["duration"], timestamp)],
                "run_count": 1,
            }
        else:
            duration_data[test_id]["durations"].append((result["duration"], timestamp))
            duration_data[test_id]["run_count"] += 1

    trends = {}
    for test_id, data in duration_data.items():
        if data["run_count"] < min_runs:
            continue

        durations = [d[0] for d in data["durations"]]
        timestamps = [d[1] for d in data["durations"]]

        # Calculate trend using linear regression
        x = [
            (t - min(timestamps)).total_seconds() / 86400 for t in timestamps
        ]  # Convert to days
        y = durations
        n = len(x)
        if n < 2:
            continue

        slope = (n * sum(x[i] * y[i] for i in range(n)) - sum(x) * sum(y)) / (
            n * sum(x[i] * x[i] for i in range(n)) - sum(x) * sum(x)
        )

        trends[test_id] = {
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "trend": slope,  # seconds/day
            "run_count": data["run_count"],
        }

    return trends


def get_stability_metrics(
    db_path: Path,
    days: int = 30,
    sut_id: Optional[str] = None,
    granularity: str = "day",
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
    results = get_test_results(db_path=db_path, start_time=since)

    # Group results by time period
    periods = {}
    for result in results:
        timestamp = (
            datetime.fromisoformat(result["timestamp"])
            if isinstance(result["timestamp"], str)
            else result["timestamp"]
        )
        if granularity == "hour":
            period = timestamp.replace(minute=0, second=0, microsecond=0)
        elif granularity == "day":
            period = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # week
            period = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            period -= timedelta(days=period.weekday())

        if period not in periods:
            periods[period] = []
        periods[period].append(result)

    stability_report = {"stability_score": [], "failure_rate": [], "flaky_tests": []}

    for period, period_results in sorted(periods.items()):
        total_tests = len(period_results)
        if total_tests == 0:
            continue

        failed = len([r for r in period_results if r["outcome"] == "failed"])

        # Identify flaky tests (tests that both passed and failed in this period)
        test_outcomes = {}
        for r in period_results:
            if r["test_id"] not in test_outcomes:
                test_outcomes[r["test_id"]] = set()
            test_outcomes[r["test_id"]].add(r["outcome"])

        flaky = {
            test_id
            for test_id, outcomes in test_outcomes.items()
            if "passed" in outcomes and "failed" in outcomes
        }

        stability_report["stability_score"].append(
            {
                "period": period,
                "score": 1.0
                - (failed / total_tests)
                - (len(flaky) / total_tests * 0.5),
            }
        )

        stability_report["failure_rate"].append(
            {"period": period, "rate": failed / total_tests}
        )

        stability_report["flaky_tests"].append(
            {"period": period, "count": len(flaky), "tests": list(flaky)}
        )

    return stability_report


def get_rerun_patterns(
    db_path: Path,
    days: int = 30,
    min_reruns: int = 5,
    sut_id: Optional[str] = None,
) -> Dict:
    """Analyze patterns in test reruns to identify successful recovery paths.

    Args:
        db_path: Path to SQLite database
        days: Number of days to analyze
        min_reruns: Minimum number of reruns required to include in analysis
        sut_id: Optional SUT ID to filter by

    Returns:
        Dict containing:
        - success_patterns: Most common outcome sequences that lead to success
        - failure_patterns: Most common outcome sequences that lead to failure
        - recovery_rate: % of tests that eventually pass after reruns
        - avg_attempts: Average number of attempts needed for success
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        query = """
        SELECT
            tr.test_id,
            tr.outcome,
            tr.rerun_outcomes,
            tr.rerun_count,
            s.start_time
        FROM test_results tr
        JOIN sessions s ON tr.session_id = s.session_id
        WHERE s.start_time >= ?
        """
        params = [cutoff.isoformat()]

        if sut_id:
            query += " AND s.sut_id = ?"
            params.append(sut_id)

        cursor.execute(query, params)
        rows = cursor.fetchall()

    if not rows:
        return {
            "success_patterns": [],
            "failure_patterns": [],
            "recovery_rate": 0.0,
            "avg_attempts": 0.0,
        }

    success_patterns = defaultdict(int)
    failure_patterns = defaultdict(int)
    total_attempts = []

    for row in rows:
        test_id, outcome, rerun_outcomes_json, rerun_count, _ = row
        rerun_outcomes = json.loads(rerun_outcomes_json)
        full_sequence = rerun_outcomes + [outcome]

        if rerun_count >= min_reruns:
            sequence = tuple(full_sequence)
            if outcome == "PASSED":
                success_patterns[sequence] += 1
            else:
                failure_patterns[sequence] += 1

        total_attempts.append(rerun_count)

    successful_reruns = sum(1 for row in rows if row[1] == "PASSED")

    return {
        "success_patterns": sorted(
            [(list(k), v) for k, v in success_patterns.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10],
        "failure_patterns": sorted(
            [(list(k), v) for k, v in failure_patterns.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10],
        "recovery_rate": (successful_reruns / len(rows) * 100),
        "avg_attempts": sum(total_attempts) / len(total_attempts),
    }


def get_xfail_trends(
    db_path: Path,
    days: int = 30,
    granularity: str = "day",
    sut_id: Optional[str] = None,
) -> List[Dict]:
    """Analyze trends in expected failures (xfail) and unexpected passes (xpass).

    Args:
        db_path: Path to SQLite database
        days: Number of days to analyze
        granularity: Time grouping ('hour', 'day', 'week')
        sut_id: Optional SUT ID to filter by

    Returns:
        List of dicts with:
        - timestamp: Time bucket
        - xfail_count: Number of expected failures
        - xpass_count: Number of unexpected passes
        - xfail_rate: % of total tests that were xfail
        - xpass_rate: % of xfails that unexpectedly passed
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # First get the raw data
        query = """
        SELECT
            tr.start_time,
            tr.outcome,
            s.total_tests
        FROM test_results tr
        JOIN sessions s ON tr.session_id = s.session_id
        WHERE tr.start_time >= ?
        AND tr.outcome IN ('XFAILED', 'XPASSED')
        """
        params = [cutoff.isoformat()]

        if sut_id:
            query += " AND s.sut_id = ?"
            params.append(sut_id)

        cursor.execute(query, params)
        rows = cursor.fetchall()

    if not rows:
        return []

    # Group by time bucket
    buckets = defaultdict(lambda: {"xfail": 0, "xpass": 0, "total": 0})

    for row in rows:
        timestamp = datetime.fromisoformat(row[0])
        outcome = row[1]
        total_tests = row[2]

        # Determine bucket based on granularity
        if granularity == "hour":
            bucket = timestamp.replace(minute=0, second=0, microsecond=0)
        elif granularity == "week":
            bucket = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            bucket -= timedelta(days=timestamp.weekday())
        else:  # default to day
            bucket = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

        buckets[bucket]["total"] = total_tests
        if outcome == "XFAILED":
            buckets[bucket]["xfail"] += 1
        else:  # XPASSED
            buckets[bucket]["xpass"] += 1

    # Convert to list of dicts with calculated rates
    trends = []
    for timestamp, counts in sorted(buckets.items()):
        total = counts["total"]
        xfails = counts["xfail"]
        xpasses = counts["xpass"]

        trends.append(
            {
                "timestamp": timestamp.isoformat(),
                "xfail_count": xfails,
                "xpass_count": xpasses,
                "xfail_rate": (xfails / total * 100) if total > 0 else 0,
                "xpass_rate": (xpasses / (xfails + xpasses) * 100)
                if (xfails + xpasses) > 0
                else 0,
            }
        )

    return trends


def get_flaky_tests(
    db_path: Path,
    days: int = 30,
    min_runs: int = 5,
    flakiness_threshold: float = 0.1,
    sut_id: Optional[str] = None,
) -> List[Dict]:
    """Identify tests that frequently flip between different outcomes.

    Args:
        db_path: Path to SQLite database
        days: Number of days to analyze
        min_runs: Minimum number of runs required to include in analysis
        flakiness_threshold: Minimum ratio of outcome changes to total runs
        sut_id: Optional SUT ID to filter by

    Returns:
        List of dicts containing:
        - test_id: Test identifier
        - run_count: Number of times the test was run
        - unique_outcomes: List of different outcomes seen
        - outcome_counts: Dict mapping outcomes to counts
        - flakiness_score: Ratio of outcome changes to total runs
        - common_transitions: Most common outcome transitions
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        query = """
        SELECT
            tr.test_id,
            tr.outcome,
            tr.start_time
        FROM test_results tr
        JOIN sessions s ON tr.session_id = s.session_id
        WHERE tr.start_time >= ?
        ORDER BY tr.test_id, tr.start_time
        """
        params = [cutoff.isoformat()]

        if sut_id:
            query += " AND s.sut_id = ?"
            params.append(sut_id)

        cursor.execute(query, params)
        rows = cursor.fetchall()

    if not rows:
        return []

    # Group by test_id
    test_outcomes = defaultdict(list)
    for row in rows:
        test_id, outcome, _ = row
        test_outcomes[test_id].append(outcome)

    flaky_tests = []
    for test_id, outcomes in test_outcomes.items():
        if len(outcomes) < min_runs:
            continue

        unique_outcomes = list(set(outcomes))

        # Count outcome transitions
        transitions = defaultdict(int)
        for i in range(len(outcomes) - 1):
            transition = (outcomes[i], outcomes[i + 1])
            if transition[0] != transition[1]:
                transitions[transition] += 1

        total_transitions = sum(transitions.values())
        flakiness_score = total_transitions / len(outcomes)

        if flakiness_score >= flakiness_threshold:
            # Count occurrences of each outcome
            outcome_counts = defaultdict(int)
            for outcome in outcomes:
                outcome_counts[outcome] += 1

            flaky_tests.append(
                {
                    "test_id": test_id,
                    "run_count": len(outcomes),
                    "unique_outcomes": unique_outcomes,
                    "outcome_counts": dict(outcome_counts),
                    "flakiness_score": flakiness_score,
                    "common_transitions": sorted(
                        [((k[0], k[1]), v) for k, v in transitions.items()],
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5],
                }
            )

    return sorted(flaky_tests, key=lambda x: x["flakiness_score"], reverse=True)


def get_rerun_stats(db_path: Path) -> Dict[str, Any]:
    """Get statistics about test reruns.

    Returns:
        Dict containing:
        - total_reruns: Number of tests that were rerun
        - avg_reruns: Average number of reruns per test
        - success_rate: Percentage of reruns that ended in success
        - avg_time: Average time spent on reruns
        - outcome_counts: Count of final outcomes for rerun tests
        - common_sequences: Most common rerun sequences
    """
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get tests with reruns
        cursor.execute(
            """
            SELECT
                test_id,
                outcome,
                duration,
                rerun_count,
                rerun_outcomes
            FROM test_results
            WHERE rerun_count > 0
        """
        )
        results = cursor.fetchall()

        if not results:
            return None

        total_reruns = len(results)
        avg_reruns = sum(r[3] for r in results) / total_reruns
        total_time = sum(r[2] * r[3] for r in results)
        avg_time = total_time / total_reruns

        # Analyze outcomes
        outcome_counts = defaultdict(int)
        successful_sequences = 0
        sequence_counts = defaultdict(int)

        for result in results:
            outcome = result[1]
            outcome_counts[outcome] += 1

            # Analyze sequence
            rerun_outcomes = json.loads(result[4]) if result[4] else []
            if rerun_outcomes:
                sequence = " → ".join(rerun_outcomes + [outcome])
                sequence_counts[sequence] += 1
                if outcome == "passed":
                    successful_sequences += 1

        success_rate = (
            (successful_sequences / total_reruns * 100) if total_reruns > 0 else 0
        )

        # Get top 10 most common sequences
        common_sequences = sorted(
            sequence_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "total_reruns": total_reruns,
            "avg_reruns": avg_reruns,
            "success_rate": success_rate,
            "avg_time": avg_time,
            "outcome_counts": dict(outcome_counts),
            "common_sequences": common_sequences,
        }


def update_session_stats(db_path: Path, session_id: str) -> None:
    """Update session statistics based on test results."""
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get all test results for the session
        cursor.execute(
            """
            SELECT outcome, rerun_count, rerun_outcomes, duration
            FROM test_results
            WHERE session_id = ?
            """,
            (session_id,),
        )
        results = cursor.fetchall()

        # Initialize counters
        stats = defaultdict(int)
        total_rerun_time = 0
        successful_reruns = 0
        total_reruns = 0

        # Calculate statistics
        for outcome, rerun_count, rerun_outcomes, duration in results:
            stats[outcome] += 1
            if rerun_count > 0:
                total_reruns += 1
                total_rerun_time += duration * rerun_count
                (json.loads(rerun_outcomes) if rerun_outcomes else [])
                if outcome == "passed":
                    successful_reruns += 1

        # Update session
        cursor.execute(
            """
            UPDATE sessions
            SET total_tests = ?,
                passed_tests = ?,
                failed_tests = ?,
                skipped_tests = ?,
                xfailed_tests = ?,
                xpassed_tests = ?,
                rerun = ?,
                rerun_recovery_rate = ?,
                rerun_total_time = ?
            WHERE session_id = ?
            """,
            (
                len(results),
                stats["passed"],
                stats["failed"],
                stats["skipped"],
                stats["xfailed"],
                stats["xpassed"],
                total_reruns,
                (successful_reruns / total_reruns * 100) if total_reruns > 0 else 0,
                total_rerun_time,
                session_id,
            ),
        )
        conn.commit()
