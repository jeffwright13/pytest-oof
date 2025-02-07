#!/usr/bin/env python3
"""Generate historical test data by back-dating and varying existing results."""
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from pytest_oof.db import init_db


def get_db_path() -> str:
    """Get path to SQLite database."""
    return str(Path("/Users/jwr003/coding/pytest-oof/oof/oof-results.db"))


def db_connection(db_path: str):
    """Create a database connection with proper settings."""
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_tables_exist():
    """Create database tables if they don't exist."""
    db_path = get_db_path()
    with db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                id TEXT PRIMARY KEY,
                sut_id TEXT,
                sut_type TEXT,
                sut_version TEXT,
                sut_env TEXT,
                sut_metadata TEXT,
                start_time TIMESTAMP,
                stop_time TIMESTAMP,
                duration REAL,
                num_tests INTEGER,
                num_tests_without_rerun INTEGER,
                num_tests_total INTEGER,
                num_passes INTEGER,
                num_failures INTEGER,
                num_errors INTEGER,
                num_skips INTEGER,
                num_xfails INTEGER,
                num_xpasses INTEGER,
                num_reruns INTEGER,
                num_rerun_groups INTEGER,
                num_warnings INTEGER,
                num_warnings_unique INTEGER,
                num_deselected INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                nodeid TEXT,
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
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            )
            """
        )
        conn.commit()


def get_db_path() -> Path:
    """Get the database path."""
    package_dir = Path(__file__).parent.parent
    db_path = package_dir / "oof/oof-results.db"
    if not db_path.exists():
        db_path = Path("oof/oof-results.db")
        # Initialize the database if it doesn't exist
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(db_path)
    print(f"Using database: {db_path}")
    return db_path


def vary_number(original: int, variance_pct: float = 0.1) -> int:
    """Vary a number by up to variance_pct percent."""
    if original == 0:
        return 0
    variance = int(original * variance_pct)
    if variance == 0:
        variance = 1
    return max(0, original + random.randint(-variance, variance))


# Define available SUT IDs
SUT_IDS = [
    "qa-ref-azulprimejdk17",
    "qa-ref-dist-core-azulprime17",
    "qa-re-openjdk17",
    "qa-ref-dist-core-openjdk17",
]


def vary_session(session: Dict[Any, Any], base_time: datetime) -> Dict[Any, Any]:
    """Create a varied version of a test session."""
    varied = session.copy()

    # Generate new session ID and random SUT ID
    varied["id"] = str(uuid.uuid4())
    varied["sut_id"] = random.choice(SUT_IDS)

    # Vary start time around base time
    start_time = base_time + timedelta(
        minutes=random.randint(-30, 30), seconds=random.randint(-30, 30)
    )
    varied["start_time"] = start_time

    # Vary duration
    duration = vary_number(session["duration"])
    varied["duration"] = duration

    # Calculate stop time based on duration
    varied["stop_time"] = start_time + timedelta(seconds=duration)

    # Vary test counts
    varied["num_tests"] = int(vary_number(session["num_tests"]))
    varied["num_passes"] = int(vary_number(session["num_passes"]))
    varied["num_failures"] = int(vary_number(session["num_failures"]))
    varied["num_errors"] = int(vary_number(session["num_errors"]))
    varied["num_skips"] = int(vary_number(session["num_skips"]))
    varied["num_xfails"] = int(vary_number(session["num_xfails"]))
    varied["num_xpasses"] = int(vary_number(session["num_xpasses"]))
    varied["num_reruns"] = int(vary_number(session["num_reruns"]))
    varied["num_rerun_groups"] = int(vary_number(session["num_rerun_groups"]))

    # Ensure test counts are consistent
    total = varied["num_tests"]
    if total > 0:
        # Calculate percentages of each outcome
        pass_pct = varied["num_passes"] / total
        fail_pct = varied["num_failures"] / total
        error_pct = varied["num_errors"] / total
        skip_pct = varied["num_skips"] / total
        xfail_pct = varied["num_xfails"] / total
        xpass_pct = varied["num_xpasses"] / total

        # Normalize percentages to sum to 1.0
        total_pct = pass_pct + fail_pct + error_pct + skip_pct + xfail_pct + xpass_pct
        if total_pct > 0:
            pass_pct /= total_pct
            fail_pct /= total_pct
            error_pct /= total_pct
            skip_pct /= total_pct
            xfail_pct /= total_pct
            xpass_pct /= total_pct

        # Apply percentages to total
        varied["num_passes"] = int(total * pass_pct)
        varied["num_failures"] = int(total * fail_pct)
        varied["num_errors"] = int(total * error_pct)
        varied["num_skips"] = int(total * skip_pct)
        varied["num_xfails"] = int(total * xfail_pct)
        varied["num_xpasses"] = int(total * xpass_pct)

    return varied


def get_test_templates():
    """Get template test cases and their possible outcomes."""
    templates = {
        "test_login_success": {
            "outcomes": ["passed"],
            "error_message": "",
            "error_type": "",
            "error_traceback": "",
            "longreprtext": "",
        },
        "test_login_invalid_password": {
            "outcomes": ["failed"],
            "error_message": "AssertionError: Login should have failed with invalid password",
            "error_type": "AssertionError",
            "error_traceback": "test_login.py:45: AssertionError",
            "longreprtext": "Expected login to fail but it succeeded",
        },
        "test_login_missing_username": {
            "outcomes": ["failed", "xfailed"],
            "error_message": "ValueError: Username cannot be empty",
            "error_type": "ValueError",
            "error_traceback": "test_login.py:60: ValueError",
            "longreprtext": "Username field was empty",
        },
        "test_database_connection": {
            "outcomes": ["passed", "failed", "error"],
            "error_message": "ConnectionError: Could not connect to database",
            "error_type": "ConnectionError",
            "error_traceback": "test_db.py:25: ConnectionError",
            "longreprtext": "Database connection timed out",
        },
        "test_api_response": {
            "outcomes": ["passed", "failed"],
            "error_message": "AssertionError: Invalid API response format",
            "error_type": "AssertionError",
            "error_traceback": "test_api.py:78: AssertionError",
            "longreprtext": "Expected JSON response but got XML",
        },
        "test_data_validation": {
            "outcomes": ["passed", "xfailed"],
            "error_message": "ValidationError: Invalid data format",
            "error_type": "ValidationError",
            "error_traceback": "test_validation.py:112: ValidationError",
            "longreprtext": "Data validation failed: missing required fields",
        },
        "test_performance": {
            "outcomes": ["passed", "failed", "skipped"],
            "error_message": "PerformanceError: Response time exceeded threshold",
            "error_type": "PerformanceError",
            "error_traceback": "test_perf.py:95: PerformanceError",
            "longreprtext": "Response time was 5.2s, exceeding 5.0s threshold",
        },
        "test_cleanup": {
            "outcomes": ["passed", "error"],
            "error_message": "RuntimeError: Failed to clean up test data",
            "error_type": "RuntimeError",
            "error_traceback": "test_cleanup.py:45: RuntimeError",
            "longreprtext": "Could not remove temporary test files",
        },
    }
    return templates


def create_template_session():
    """Create a template test session."""
    now = datetime.now()
    session = {
        "id": str(uuid.uuid4()),
        "start_time": now,
        "stop_time": now + timedelta(minutes=5),
        "duration": 300.0,  # 5 minutes
        "sut_id": random.choice(SUT_IDS),
        "sut_type": "java",
        "sut_version": "17.0.0",
        "sut_env": "linux",
        "num_tests": 100,
        "num_passes": 80,
        "num_failures": 10,
        "num_errors": 5,
        "num_skips": 2,
        "num_xfails": 2,
        "num_xpasses": 1,
        "num_reruns": 0,
        "num_rerun_groups": 0,
    }
    return session


def update_session_stats(session_id: str, test_results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Update session stats based on test results."""
    stats = {"num_reruns": 0, "num_rerun_groups": 0}

    # Count reruns
    for result in test_results:
        if result.get("is_rerun", False):
            stats["num_reruns"] += 1

    # Count rerun groups (consecutive reruns)
    in_rerun_group = False
    for result in test_results:
        if result.get("is_rerun", False):
            if not in_rerun_group:
                stats["num_rerun_groups"] += 1
                in_rerun_group = True
        else:
            in_rerun_group = False

    return stats


def generate_test_results(session_id: str, num_tests: int, base_time: datetime):
    """Generate test results for a session."""
    test_results = []
    test_templates = get_test_templates()

    for i in range(num_tests):
        test_template = random.choice(list(test_templates.items()))
        test_id = test_template[0]
        template_data = test_template[1]
        outcome = random.choice(template_data["outcomes"])

        # Vary the timestamp within 5 minutes of base time
        timestamp = base_time + timedelta(
            minutes=random.randint(0, 5),
            seconds=random.randint(0, 59),
            microseconds=random.randint(0, 999999),
        )

        # Create test result
        result = {
            "session_id": session_id,
            "nodeid": test_id,
            "outcome": outcome,
            "start_time": timestamp.isoformat(),
            "duration": random.uniform(0.1, 5.0),
            "error_message": template_data["error_message"] if outcome in ["failed", "error"] else "",
            "error_type": template_data["error_type"] if outcome in ["failed", "error"] else "",
            "error_traceback": template_data["error_traceback"] if outcome in ["failed", "error"] else "",
            "has_warning": random.random() < 0.1,  # 10% chance of warning
            "longreprtext": template_data["longreprtext"] if outcome in ["failed", "error"] else "",
            "caplog": f"[{timestamp}] Test log output for {test_id}",
            "capstdout": f"Test stdout for {test_id}",
            "capstderr": f"Test stderr for {test_id}" if outcome in ["failed", "error"] else "",
            "rerun_count": 0,
        }

        test_results.append(result)

    return test_results


def ensure_template_data():
    """Ensure template data exists in database."""
    db_path = get_db_path()
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get template session
        cursor.execute(
            """
            SELECT
                id, start_time, stop_time, duration,
                sut_id, sut_type, sut_version, sut_env,
                num_tests, num_passes, num_failures,
                num_errors, num_skips, num_xfails, num_xpasses,
                num_reruns, num_rerun_groups
            FROM test_sessions
            ORDER BY start_time DESC
            LIMIT 1
            """
        )
        template = cursor.fetchone()

        if not template:
            # Create a template session
            session_id = str(uuid.uuid4())
            start_time = datetime.now() - timedelta(days=1)
            template_session = {
                "id": session_id,
                "start_time": start_time,
                "stop_time": start_time + timedelta(minutes=30),
                "duration": 1800.0,
                "sut_id": "qa-ref-dist-core-openjdk17",
                "sut_type": "java",
                "sut_version": "17.0.1",
                "sut_env": "linux",
                "num_tests": 100,
                "num_passes": 80,
                "num_failures": 10,
                "num_errors": 5,
                "num_skips": 2,
                "num_xfails": 2,
                "num_xpasses": 1,
                "num_reruns": 0,
                "num_rerun_groups": 0,
            }

            # First insert the session
            cursor.execute(
                """
                INSERT INTO test_sessions (
                    id, start_time, stop_time, duration,
                    sut_id, sut_type, sut_version, sut_env,
                    num_tests, num_passes, num_failures,
                    num_errors, num_skips, num_xfails, num_xpasses,
                    num_reruns, num_rerun_groups
                ) VALUES (
                    :id, :start_time, :stop_time, :duration,
                    :sut_id, :sut_type, :sut_version, :sut_env,
                    :num_tests, :num_passes, :num_failures,
                    :num_errors, :num_skips, :num_xfails, :num_xpasses,
                    :num_reruns, :num_rerun_groups
                )
                """,
                template_session,
            )
            conn.commit()

            # Then generate and insert test results
            test_results = generate_test_results(
                session_id=session_id,
                num_tests=template_session["num_tests"],
                base_time=template_session["start_time"],
            )

            for result in test_results:
                cursor.execute(
                    """
                    INSERT INTO test_results (
                        session_id, nodeid, outcome, start_time,
                        duration, error_message, error_type,
                        error_traceback, has_warning, longreprtext,
                        caplog, capstdout, capstderr, rerun_count
                    ) VALUES (
                        :session_id, :nodeid, :outcome, :start_time,
                        :duration, :error_message, :error_type,
                        :error_traceback, :has_warning, :longreprtext,
                        :caplog, :capstdout, :capstderr, :rerun_count
                    )
                    """,
                    result,
                )
            conn.commit()

            # Fetch the newly created template
            cursor.execute(
                """
                SELECT
                    id, start_time, stop_time, duration,
                    sut_id, sut_type, sut_version, sut_env,
                    num_tests, num_passes, num_failures,
                    num_errors, num_skips, num_xfails, num_xpasses,
                    num_reruns, num_rerun_groups
                FROM test_sessions
                ORDER BY start_time DESC
                LIMIT 1
                """
            )
            template = cursor.fetchone()

        return template


def generate_historical_data(days: int = 7, sessions_per_day: tuple = (3, 8)):
    """Generate historical test data."""
    db_path = get_db_path()
    ensure_template_data()

    # Connect to database
    conn = db_connection(db_path)
    try:
        cursor = conn.cursor()

        # Get template session
        cursor.execute(
            """
            SELECT
                id, start_time, stop_time, duration,
                sut_id, sut_type, sut_version, sut_env,
                num_tests, num_passes, num_failures,
                num_errors, num_skips, num_xfails, num_xpasses,
                num_reruns, num_rerun_groups
            FROM test_sessions
            ORDER BY start_time DESC
            LIMIT 1
            """
        )
        template = cursor.fetchone()

        if not template:
            template = ensure_template_data()

        # Convert to dict for easier manipulation
        template_session = {
            "id": template[0],
            "start_time": datetime.fromisoformat(template[1]),
            "stop_time": datetime.fromisoformat(template[2]) if template[2] else None,
            "duration": template[3],
            "sut_id": template[4],
            "sut_type": template[5],
            "sut_version": template[6],
            "sut_env": template[7],
            "num_tests": template[8],
            "num_passes": template[9],
            "num_failures": template[10],
            "num_errors": template[11],
            "num_skips": template[12],
            "num_xfails": template[13],
            "num_xpasses": template[14],
            "num_reruns": template[15],
            "num_rerun_groups": template[16],
        }

        # Start from current time and work backwards
        current_time = datetime.now()
        all_sessions = []
        all_test_results = []
        total_reruns = 0
        total_rerun_groups = 0

        # Generate data for each day
        for day in range(days):
            # Define business hours for this day (8 AM to 6 PM)
            day_start = current_time.replace(hour=8, minute=0, second=0, microsecond=0)
            day_end = current_time.replace(hour=18, minute=0, second=0, microsecond=0)
            
            # Randomly determine number of sessions for this day
            num_sessions = random.randint(sessions_per_day[0], sessions_per_day[1])
            
            # Generate session times spread throughout the day
            session_times = []
            for _ in range(num_sessions):
                # Generate a random time between business hours
                minutes_offset = random.randint(0, int((day_end - day_start).total_seconds() / 60))
                session_time = day_start + timedelta(minutes=minutes_offset)
                # Add some natural variation (1-10 minutes) to avoid exact intervals
                natural_variation = timedelta(minutes=random.uniform(1, 10))
                session_time += natural_variation
                session_times.append(session_time)
            
            # Sort times to maintain chronological order
            session_times.sort()

            # Generate sessions for each time
            for session_time in session_times:
                # Randomly select a SUT for this session
                sut_id = random.choice(SUT_IDS)

                # Create session with the template
                session = vary_session(template_session, session_time)
                session["sut_id"] = sut_id

                # Insert session
                cursor.execute(
                    """
                    INSERT INTO test_sessions (
                        id, sut_id, sut_type, sut_version, sut_env,
                        sut_metadata, start_time, stop_time, duration,
                        num_tests, num_tests_without_rerun, num_tests_total,
                        num_passes, num_failures, num_errors, num_skips,
                        num_xfails, num_xpasses, num_reruns, num_rerun_groups
                    ) VALUES (
                        :id, :sut_id, :sut_type, :sut_version, :sut_env,
                        :sut_metadata, :start_time, :stop_time, :duration,
                        :num_tests, :num_tests_without_rerun, :num_tests_total,
                        :num_passes, :num_failures, :num_errors, :num_skips,
                        :num_xfails, :num_xpasses, :num_reruns, :num_rerun_groups
                    )
                    """,
                    {
                        "id": session["id"],
                        "sut_id": session["sut_id"],
                        "sut_type": session["sut_type"],
                        "sut_version": session["sut_version"],
                        "sut_env": session["sut_env"],
                        "sut_metadata": json.dumps({"key": "value"}),
                        "start_time": session["start_time"],
                        "stop_time": session["stop_time"],
                        "duration": session["duration"],
                        "num_tests": session["num_tests"],
                        "num_tests_without_rerun": session["num_tests"],
                        "num_tests_total": session["num_tests"],
                        "num_passes": session["num_passes"],
                        "num_failures": session["num_failures"],
                        "num_errors": session["num_errors"],
                        "num_skips": session["num_skips"],
                        "num_xfails": session["num_xfails"],
                        "num_xpasses": session["num_xpasses"],
                        "num_reruns": session["num_reruns"],
                        "num_rerun_groups": session["num_rerun_groups"],
                    },
                )
                session_id = cursor.lastrowid
                all_sessions.append(session)

                # Generate test results for this session
                test_results = generate_test_results(
                    session_id=session_id,
                    num_tests=session["num_tests"],
                    base_time=session["start_time"],
                )
                all_test_results.extend(test_results)

                # Update session stats
                session_stats = update_session_stats(session_id, test_results)
                total_reruns += session_stats["num_reruns"]
                total_rerun_groups += session_stats["num_rerun_groups"]

                cursor.execute(
                    """
                    UPDATE test_sessions
                    SET num_reruns = :num_reruns, num_rerun_groups = :num_rerun_groups
                    WHERE id = :session_id
                    """,
                    {
                        "num_reruns": session_stats["num_reruns"],
                        "num_rerun_groups": session_stats["num_rerun_groups"],
                        "session_id": session_id,
                    },
                )

            current_time -= timedelta(days=1)

        # Print summary
        print(f"\nInserting {len(all_sessions)} new sessions...")
        print(f"\nInserting {len(all_test_results)} test results...")
        print(f"\nTotal reruns: {total_reruns}")
        print(f"Total rerun groups: {total_rerun_groups}")
        print(
            f"\nSuccessfully generated {len(all_sessions)} historical test sessions with {len(all_test_results)} test results over {days} days"
        )

        # Insert all test results
        for result in all_test_results:
            cursor.execute(
                """
                INSERT INTO test_results (
                    session_id, nodeid, outcome, start_time,
                    duration, error_message, error_type,
                    error_traceback, has_warning, longreprtext,
                    caplog, capstdout, capstderr, rerun_count
                ) VALUES (
                    :session_id, :nodeid, :outcome, :start_time,
                    :duration, :error_message, :error_type,
                    :error_traceback, :has_warning, :longreprtext,
                    :caplog, :capstdout, :capstderr, :rerun_count
                )
                """,
                {
                    "session_id": result["session_id"],
                    "nodeid": result["nodeid"],
                    "outcome": result["outcome"],
                    "start_time": result["start_time"],
                    "duration": result.get("duration", 0.0),
                    "error_message": result.get("error_message", ""),
                    "error_type": result.get("error_type", ""),
                    "error_traceback": result.get("error_traceback", ""),
                    "has_warning": result.get("has_warning", False),
                    "longreprtext": result.get("longreprtext", ""),
                    "caplog": result.get("caplog", ""),
                    "capstdout": result.get("capstdout", ""),
                    "capstderr": result.get("capstderr", ""),
                    "rerun_count": result.get("rerun_count", 0),
                },
            )

        conn.commit()
    finally:
        conn.close()


def purge_database():
    """Purge all data from the database."""
    db_path = get_db_path()
    conn = db_connection(db_path)
    try:
        print("Purging database...")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM test_results")
        cursor.execute("DELETE FROM test_sessions")
        conn.commit()

        # Get counts after purge
        cursor.execute("SELECT COUNT(*) FROM test_sessions")
        sessions_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM test_results")
        results_count = cursor.fetchone()[0]

        print(
            f"Database purged. Remaining sessions: {sessions_count}, remaining results: {results_count}"
        )
    finally:
        conn.close()


def generate_test_session(base_time: datetime, template_session_id: str) -> str:
    """Generate a test session with random variations."""
    session_id = str(uuid.uuid4())
    stop_time = base_time + timedelta(minutes=random.randint(20, 40))

    # Generate test results first
    num_tests = random.randint(50, 100)
    test_results = generate_test_results(session_id, num_tests, base_time)

    # Calculate session stats from actual test results
    num_passes = sum(1 for r in test_results if r["outcome"].lower() == "passed")
    num_failures = sum(1 for r in test_results if r["outcome"].lower() == "failed")
    num_errors = sum(1 for r in test_results if r["outcome"].lower() == "error")
    num_skips = sum(1 for r in test_results if r["outcome"].lower() == "skipped")
    num_xfails = sum(1 for r in test_results if r["outcome"].lower() == "xfailed")
    num_xpasses = sum(1 for r in test_results if r["outcome"].lower() == "xpassed")
    num_warnings = sum(1 for r in test_results if r["has_warning"])

    # Pick a random SUT ID
    sut_id = random.choice(SUT_IDS)

    # Create session with calculated stats
    db_path = get_db_path()
    with db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO test_sessions (
                id,
                sut_id,
                sut_type,
                sut_version,
                sut_env,
                sut_metadata,
                start_time,
                stop_time,
                duration,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                sut_id,
                "web-service",  # sut_type
                "1.0.0",  # sut_version
                "staging",  # sut_env
                json.dumps({"key": "value"}),  # sut_metadata
                base_time.isoformat(),
                stop_time.isoformat(),
                (stop_time - base_time).total_seconds(),
                len(test_results),  # Use actual number of test results
                len(test_results),  # num_tests_without_rerun
                len(test_results),  # num_tests_total
                num_passes,
                num_failures,
                num_errors,
                num_skips,
                num_xfails,
                num_xpasses,
                0,  # num_reruns
                0,  # num_rerun_groups
                num_warnings,
                num_warnings,  # num_warnings_unique
                0,  # num_deselected
            ),
        )
        conn.commit()

    return session_id


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate historical test data")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to generate data for (default: %(default)s)",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Purge existing data before generating new data",
    )
    args = parser.parse_args()

    if args.purge:
        purge_database()
    else:
        generate_historical_data(
            days=args.days,
            sessions_per_day=(3, 8),
        )
