#!/usr/bin/env python3
"""Generate historical test data by back-dating and varying existing results."""
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from pytest_oof.db import init_db


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
    varied["session_id"] = str(uuid.uuid4())
    varied["sut_id"] = random.choice(SUT_IDS)

    # Print debug info
    print("\nTemplate session values:")
    for k, v in varied.items():
        if k in [
            "sut_id",
            "num_tests",
            "num_passes",
            "num_failures",
            "num_errors",
            "num_skips",
            "num_xfails",
            "num_xpasses",
        ]:
            print(f"{k}: {v}")

    # Vary the test counts (maintain consistency)
    total = int(varied["num_tests"] or 0)  # Handle NULL
    passed = int(varied["num_passes"] or 0)
    failed = int(varied["num_failures"] or 0)
    errors = int(varied["num_errors"] or 0)
    skipped = int(varied["num_skips"] or 0)

    # Calculate new counts while maintaining reasonable proportions
    new_total = vary_number(total, 0.25)
    ratio = new_total / total if total > 0 else 1

    # Add XF and XP results
    xf_ratio = random.uniform(0.05, 0.15)  # 5-15% of failures will be XF
    xp_ratio = random.uniform(0.05, 0.15)  # 5-15% of passes will be XP

    new_passed = int(passed * ratio * random.uniform(0.95, 1.05))
    new_failed = int(failed * ratio * random.uniform(0.9, 1.1))
    new_errors = int(errors * ratio * random.uniform(0.9, 1.1))
    new_skipped = int(skipped * ratio * random.uniform(0.9, 1.1))

    # Calculate XF and XP counts
    new_xf = int(new_failed * xf_ratio)
    new_xp = int(new_passed * xp_ratio)

    # Adjust regular passes and failures
    new_failed -= new_xf
    new_passed -= new_xp

    # Ensure totals add up
    while (
        new_passed + new_failed + new_errors + new_skipped + new_xf + new_xp
    ) != new_total:
        diff = new_total - (
            new_passed + new_failed + new_errors + new_skipped + new_xf + new_xp
        )
        if diff > 0:
            new_passed += diff
        else:
            new_passed = max(0, new_passed + diff)

    varied["num_tests"] = new_total
    varied["num_passes"] = new_passed
    varied["num_failures"] = new_failed
    varied["num_errors"] = new_errors
    varied["num_skips"] = new_skipped
    varied["num_xfails"] = new_xf
    varied["num_xpasses"] = new_xp

    # Vary the duration (handle NULL values)
    base_duration = float(
        varied.get("duration", 10.0) or 10.0
    )  # Default to 10 seconds if NULL or NaN
    if pd.isna(base_duration):
        base_duration = 10.0
    varied["duration"] = base_duration * random.uniform(0.9, 1.1)

    # Set the timestamps
    varied["start_time"] = base_time
    varied["end_time"] = base_time + timedelta(seconds=int(varied["duration"]))

    # Handle potentially NULL fields
    varied["sut_type"] = varied.get("sut_type", "") or ""
    varied["sut_version"] = varied.get("sut_version", "") or ""
    varied["sut_env"] = varied.get("sut_env", "") or ""

    # Print final values for verification
    print("\nGenerated session values:")
    for k, v in varied.items():
        if k in [
            "sut_id",
            "num_tests",
            "num_passes",
            "num_failures",
            "num_errors",
            "num_skips",
            "num_xfails",
            "num_xpasses",
        ]:
            print(f"{k}: {v}")

    return varied


def get_test_templates():
    """Get template test cases and their possible outcomes."""
    return {
        # Basic outcomes
        "demo-tests/test_0.py::test0_pass_1": ["PASSED"],
        "demo-tests/test_0.py::test0_fail_1": ["FAILED"],
        "demo-tests/test_0.py::test0_pass_2_logs": ["PASSED"],
        "demo-tests/test_0.py::test0_pass_3_error_in_fixture": ["ERROR"],
        "demo-tests/test_0.py::test0_skip": ["PASSED", "SKIPPED"],
        "demo-tests/test_0.py::test0_warning": ["WARNING", "PASSED"],
        "demo-tests/test_0.py::test0_xfail": ["XFAIL"],
        "demo-tests/test_0.py::test0_xpass": ["XPASS"],
        # Flaky tests
        "demo-tests/test_flaky_3": ["FAILED", "PASSED"],
        "demo-tests/test_1.py::test_flaky_1": ["FAILED", "PASSED"],
        "demo-tests/test_1.py::test_flaky_2": ["FAILED", "PASSED"],
        "demo-tests/test_1.py::test_flaky_3": ["FAILED", "PASSED"],
        "demo-tests/test_1.py::test_flaky_always_fail": ["FAILED"],
        "demo-tests/test_1.py::test_flaky_always_pass": ["PASSED"],
        # Tests with warnings
        "demo-tests/test_warnings.py::test_1_fails_with_warnings": [
            "WARNING",
            "FAILED",
        ],
        "demo-tests/test_warnings.py::test_2_passes_with_warnings": [
            "WARNING",
            "PASSED",
        ],
        "demo-tests/test_errors.py::test_fails_with_warnings": ["WARNING", "FAILED"],
        "demo-tests/test_errors.py::test_passes_with_warnings": ["WARNING", "PASSED"],
        # Tests with errors
        "demo-tests/test_1.py::test_14_causes_error_pass_stderr_stdout_stdlog": [
            "ERROR"
        ],
        "demo-tests/test_1.py::test_15_causes_error_fail_stderr_stdout_stdlog": [
            "ERROR"
        ],
        "demo-tests/test_2.py::test_c_error": ["ERROR"],
        "demo-tests/test_issue_1004.py::test_foo": ["ERROR", "PASSED"],
        "demo-tests/test_issue_1004.py::test_foo2": ["ERROR", "FAILED"],
        # Regular tests
        "demo-tests/test_1.py::test_a_ok": ["PASSED"],
        "demo-tests/test_1.py::test_b_fail": ["FAILED"],
        "demo-tests/test_1.py::test_c_error": ["ERROR", "PASSED"],
        "demo-tests/test_1.py::test_d1_skip_inline": ["SKIPPED"],
    }


def create_template_session():
    """Create a template test session."""
    now = datetime.now()
    session = {
        "session_id": str(uuid.uuid4()),
        "start_time": now,
        "end_time": now + timedelta(minutes=5),
        "duration": 300.0,  # 5 minutes
        "sut_id": random.choice(SUT_IDS),
        "sut_type": "java",
        "sut_version": "17.0.1",
        "sut_env": "qa",
        "num_tests": 15,
        "num_passes": 11,
        "num_failures": 2,
        "num_errors": 1,
        "num_skips": 0,
        "num_xfails": 0,
        "num_xpasses": 1,
        "num_reruns": 0,  # Will be calculated based on actual test results
        "num_rerun_groups": 0,  # Will be calculated based on actual test results
    }
    return session


def update_session_stats(session_id: int, test_results: list) -> dict:
    """Update session statistics based on test results."""
    stats = {
        "num_tests": 0,
        "num_passes": 0,
        "num_failures": 0,
        "num_errors": 0,
        "num_skips": 0,
        "num_xfails": 0,
        "num_xpasses": 0,
        "num_warnings": 0,
        "num_reruns": 0,
        "num_rerun_groups": 0,
        "flaky_test_count": 0,
        "max_rerun_count": 0,
        "total_rerun_time": 0.0,
    }

    # Track tests that had reruns
    rerun_tests = set()
    flaky_tests = set()

    for result in test_results:
        if not result["is_rerun"]:
            # Count initial test runs only
            stats["num_tests"] += 1
            outcome = result["outcome"]
            if outcome == "PASSED":
                stats["num_passes"] += 1
            elif outcome == "FAILED":
                stats["num_failures"] += 1
            elif outcome == "ERROR":
                stats["num_errors"] += 1
            elif outcome == "SKIPPED":
                stats["num_skips"] += 1
            elif outcome == "XFAIL":
                stats["num_xfails"] += 1
            elif outcome == "XPASS":
                stats["num_xpasses"] += 1

            if result["has_warning"]:
                stats["num_warnings"] += 1

            if result["rerun_count"] > 0:
                rerun_tests.add(result["test_id"])
                stats["max_rerun_count"] = max(
                    stats["max_rerun_count"], result["rerun_count"]
                )
                stats["total_rerun_time"] += result.get("total_rerun_time", 0)

            if result.get("is_flaky", False):
                flaky_tests.add(result["test_id"])
        else:
            # Count reruns
            stats["num_reruns"] += 1

    stats["num_rerun_groups"] = len(rerun_tests)
    stats["flaky_test_count"] = len(flaky_tests)
    return stats


def generate_test_results(session_id: int, num_tests: int, base_time: datetime):
    """Generate test results for a session."""
    test_templates = get_test_templates()
    results = []

    for i in range(num_tests):
        test_id = random.choice(list(test_templates.keys()))
        possible_outcomes = test_templates[test_id]
        outcome = random.choice(possible_outcomes)

        # Base test result
        timestamp = base_time + timedelta(seconds=random.uniform(0, 300))
        duration = random.uniform(0.1, 2.0)
        error_message = None
        error_type = None
        has_warning = random.random() < 0.1

        if outcome in ["FAILED", "ERROR"]:
            error_type = "AssertionError" if outcome == "FAILED" else "RuntimeError"
            error_message = f"Test {test_id} failed with {error_type}"

        rerun_outcomes = []
        rerun_durations = []
        rerun_error_messages = []
        total_rerun_time = 0
        is_flaky = False
        final_outcome = outcome

        # Generate reruns for failed/error tests with 20% probability
        rerun_count = 0
        if outcome in ["FAILED", "ERROR"] and random.random() < 0.2:
            rerun_count = random.randint(1, 3)
            for rerun_num in range(rerun_count):
                # 40% chance of passing on rerun
                rerun_outcome = "PASSED" if random.random() < 0.4 else outcome
                rerun_duration = random.uniform(0.1, 2.0)
                rerun_error = None

                if rerun_outcome in ["FAILED", "ERROR"]:
                    rerun_error = f"Test {test_id} failed on rerun {rerun_num + 1}"

                rerun_outcomes.append(rerun_outcome)
                rerun_durations.append(rerun_duration)
                rerun_error_messages.append(rerun_error)
                total_rerun_time += rerun_duration

                # Add the rerun result
                results.append(
                    {
                        "session_id": session_id,
                        "test_id": test_id,
                        "outcome": rerun_outcome,
                        "timestamp": timestamp
                        + timedelta(seconds=random.uniform(0.1, 1.0)),
                        "duration": rerun_duration,
                        "error_message": rerun_error,
                        "error_type": error_type
                        if rerun_outcome in ["FAILED", "ERROR"]
                        else None,
                        "has_warning": random.random() < 0.1,
                        "is_rerun": True,
                        "rerun_number": rerun_num + 1,
                        "rerun_count": rerun_count,
                        "rerun_outcomes": None,
                        "rerun_durations": None,
                        "rerun_error_messages": None,
                        "is_flaky": False,
                        "final_outcome": None,
                        "total_rerun_time": None,
                    }
                )

            # Update flaky status and final outcome
            if any(o == "PASSED" for o in rerun_outcomes):
                is_flaky = True
                final_outcome = "PASSED"

        # Store rerun data as JSON strings
        rerun_outcomes_str = json.dumps(rerun_outcomes) if rerun_outcomes else None
        rerun_durations_str = json.dumps(rerun_durations) if rerun_durations else None
        rerun_error_messages_str = (
            json.dumps(rerun_error_messages) if rerun_error_messages else None
        )

        # Add the original test result
        results.append(
            {
                "session_id": session_id,
                "test_id": test_id,
                "outcome": outcome,
                "timestamp": timestamp,
                "duration": duration,
                "error_message": error_message,
                "error_type": error_type,
                "has_warning": has_warning,
                "is_rerun": False,
                "rerun_number": 0,
                "rerun_count": rerun_count,
                "rerun_outcomes": rerun_outcomes_str,
                "rerun_durations": rerun_durations_str,
                "rerun_error_messages": rerun_error_messages_str,
                "is_flaky": is_flaky,
                "final_outcome": final_outcome if rerun_count > 0 else outcome,
                "total_rerun_time": total_rerun_time if rerun_count > 0 else 0,
            }
        )

    return results


def ensure_template_data():
    """Ensure there is at least one template session in the database."""
    db_path = get_db_path()
    # Initialize the database if it doesn't exist
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Check if we have any sessions
        try:
            cursor.execute("SELECT COUNT(*) FROM test_sessions")
            count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            # Table doesn't exist, initialize the database
            init_db(db_path)
            cursor.execute("SELECT COUNT(*) FROM test_sessions")
            count = cursor.fetchone()[0]

        if count == 0:
            print("\nNo template data found, creating initial template...")
            template = create_template_session()

            cursor.execute(
                """
                INSERT INTO test_sessions (
                    session_id, start_time, end_time, duration,
                    sut_id, sut_type, sut_version, sut_env,
                    num_tests, num_passes, num_failures,
                    num_errors, num_skips, num_xfails, num_xpasses,
                    num_reruns, num_rerun_groups
                ) VALUES (
                    :session_id, :start_time, :end_time, :duration,
                    :sut_id, :sut_type, :sut_version, :sut_env,
                    :num_tests, :num_passes, :num_failures,
                    :num_errors, :num_skips, :num_xfails, :num_xpasses,
                    :num_reruns, :num_rerun_groups
                )
                """,
                template,
            )

            # Get the session ID
            session_id = cursor.lastrowid

            # Generate test results for the template
            test_results = generate_test_results(
                session_id=session_id,
                num_tests=template["num_tests"],
                base_time=template["start_time"],
            )

            # Update session stats
            session_stats = update_session_stats(session_id, test_results)
            cursor.execute(
                """
                UPDATE test_sessions
                SET num_reruns = :num_reruns, num_rerun_groups = :num_rerun_groups
                WHERE session_id = :session_id
                """,
                {
                    "num_reruns": session_stats["num_reruns"],
                    "num_rerun_groups": session_stats["num_rerun_groups"],
                    "session_id": session_id,
                },
            )

            # Insert test results
            for result in test_results:
                cursor.execute(
                    """
                    INSERT INTO test_results (
                        session_id, test_id, outcome, timestamp,
                        duration, error_message, error_type, has_warning,
                        is_rerun, rerun_number, rerun_count,
                        rerun_outcomes, rerun_durations, rerun_error_messages,
                        is_flaky, final_outcome, total_rerun_time
                    ) VALUES (
                        :session_id, :test_id, :outcome, :timestamp,
                        :duration, :error_message, :error_type, :has_warning,
                        :is_rerun, :rerun_number, :rerun_count,
                        :rerun_outcomes, :rerun_durations, :rerun_error_messages,
                        :is_flaky, :final_outcome, :total_rerun_time
                    )
                    """,
                    result,
                )

            conn.commit()
    finally:
        conn.close()


def generate_historical_data(days: int = 7, sessions_per_day: tuple = (3, 8)):
    """Generate historical test data."""
    db_path = get_db_path()
    ensure_template_data()

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get template session
    cursor.execute(
        """
        SELECT
            session_id, start_time, end_time, duration,
            sut_id, sut_type, sut_version, sut_env,
            num_tests, num_passes, num_failures,
            num_errors, num_skips, num_xfails, num_xpasses,
            num_reruns, num_rerun_groups
        FROM test_sessions
        ORDER BY start_time DESC
        LIMIT 10
        """
    )
    template = cursor.fetchone()

    # Generate historical data
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    current_time = start_time

    # Store all sessions and test results to insert in bulk
    all_sessions = []
    all_test_results = []

    total_reruns = 0
    total_rerun_groups = 0

    while current_time < end_time:
        # Generate 3-8 sessions per day
        num_sessions = random.randint(sessions_per_day[0], sessions_per_day[1])

        for _ in range(num_sessions):
            # Create session with some variance
            session = vary_session(
                dict(
                    zip(
                        [
                            "session_id",
                            "start_time",
                            "end_time",
                            "duration",
                            "sut_id",
                            "sut_type",
                            "sut_version",
                            "sut_env",
                            "num_tests",
                            "num_passes",
                            "num_failures",
                            "num_errors",
                            "num_skips",
                            "num_xfails",
                            "num_xpasses",
                            "num_reruns",
                            "num_rerun_groups",
                        ],
                        template,
                    )
                ),
                current_time,
            )

            # Print session values
            if len(all_sessions) == 0:
                print("\nGenerated session values:")
                print(f"sut_id: {session['sut_id']}")
                print(f"num_tests: {session['num_tests']}")
                print(f"num_passes: {session['num_passes']}")
                print(f"num_failures: {session['num_failures']}")
                print(f"num_errors: {session['num_errors']}")
                print(f"num_skips: {session['num_skips']}")
                print(f"num_xfails: {session['num_xfails']}")
                print(f"num_xpasses: {session['num_xpasses']}\n")

            # Insert session
            cursor.execute(
                """
                INSERT INTO test_sessions (
                    session_id, start_time, end_time, duration,
                    sut_id, sut_type, sut_version, sut_env,
                    num_tests, num_passes, num_failures,
                    num_errors, num_skips, num_xfails, num_xpasses,
                    num_reruns, num_rerun_groups
                ) VALUES (
                    :session_id, :start_time, :end_time, :duration,
                    :sut_id, :sut_type, :sut_version, :sut_env,
                    :num_tests, :num_passes, :num_failures,
                    :num_errors, :num_skips, :num_xfails, :num_xpasses,
                    :num_reruns, :num_rerun_groups
                )
                """,
                session,
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

        current_time += timedelta(days=1)

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
                session_id, test_id, outcome, timestamp,
                duration, error_message, error_type, has_warning,
                is_rerun, rerun_number, rerun_count,
                rerun_outcomes, rerun_durations, rerun_error_messages,
                is_flaky, final_outcome, total_rerun_time
            ) VALUES (
                :session_id, :test_id, :outcome, :timestamp,
                :duration, :error_message, :error_type, :has_warning,
                :is_rerun, :rerun_number, :rerun_count,
                :rerun_outcomes, :rerun_durations, :rerun_error_messages,
                :is_flaky, :final_outcome, :total_rerun_time
            )
            """,
            result,
        )

    conn.commit()
    conn.close()


def purge_database():
    """Purge all data from the database."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Purging database...")
    cursor.execute("DELETE FROM test_results")
    cursor.execute("DELETE FROM test_sessions")
    conn.commit()

    # Get counts after purge
    cursor.execute("SELECT COUNT(*) FROM test_sessions")
    sessions_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM test_results")
    results_count = cursor.fetchone()[0]

    conn.close()
    print(
        f"Database purged. Remaining sessions: {sessions_count}, remaining results: {results_count}"
    )


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
        "--min-sessions",
        type=int,
        default=3,
        help="Minimum number of sessions per day (default: %(default)s)",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=8,
        help="Maximum number of sessions per day (default: %(default)s)",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Purge existing data before generating new data",
    )

    args = parser.parse_args()

    if args.purge:
        purge_database()

    generate_historical_data(
        days=args.days, sessions_per_day=(args.min_sessions, args.max_sessions)
    )
