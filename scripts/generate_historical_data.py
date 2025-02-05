#!/usr/bin/env python3
"""Generate historical test data by back-dating and varying existing results."""
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd


def get_db_path() -> Path:
    """Get the database path."""
    package_dir = Path(__file__).parent.parent
    db_path = package_dir / "oof/oof-results.db"
    if not db_path.exists():
        db_path = Path("oof/oof-results.db")
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
    "qa-ref-dist-core-openjdk17"
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
        if k in ["sut_id", "num_tests", "num_passes", "num_failures", "num_errors", "num_skips", "num_xfails", "num_xpasses"]:
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
    while (new_passed + new_failed + new_errors + new_skipped + new_xf + new_xp) != new_total:
        diff = new_total - (new_passed + new_failed + new_errors + new_skipped + new_xf + new_xp)
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
    base_duration = float(varied.get("duration", 10.0) or 10.0)  # Default to 10 seconds if NULL or NaN
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
        if k in ["sut_id", "num_tests", "num_passes", "num_failures", "num_errors", "num_skips", "num_xfails", "num_xpasses"]:
            print(f"{k}: {v}")

    return varied


def get_test_templates():
    """Get template test cases and their possible outcomes."""
    return {
        # Basic outcomes
        'demo-tests/test_0.py::test0_pass_1': ['PASSED'],
        'demo-tests/test_0.py::test0_fail_1': ['FAILED'],
        'demo-tests/test_0.py::test0_pass_2_logs': ['PASSED'],
        'demo-tests/test_0.py::test0_pass_3_error_in_fixture': ['ERROR'],
        'demo-tests/test_0.py::test0_skip': ['PASSED', 'SKIPPED'],
        'demo-tests/test_0.py::test0_warning': ['WARNING', 'PASSED'],
        'demo-tests/test_0.py::test0_xfail': ['XFAIL'],
        'demo-tests/test_0.py::test0_xpass': ['XPASS'],
        
        # Flaky tests
        'demo-tests/test_flaky_3': ['FAILED', 'PASSED'],
        'demo-tests/test_1.py::test_flaky_1': ['FAILED', 'PASSED'],
        'demo-tests/test_1.py::test_flaky_2': ['FAILED', 'PASSED'],
        'demo-tests/test_1.py::test_flaky_3': ['FAILED', 'PASSED'],
        'demo-tests/test_1.py::test_flaky_always_fail': ['FAILED'],
        'demo-tests/test_1.py::test_flaky_always_pass': ['PASSED'],
        
        # Tests with warnings
        'demo-tests/test_warnings.py::test_1_fails_with_warnings': ['WARNING', 'FAILED'],
        'demo-tests/test_warnings.py::test_2_passes_with_warnings': ['WARNING', 'PASSED'],
        'demo-tests/test_errors.py::test_fails_with_warnings': ['WARNING', 'FAILED'],
        'demo-tests/test_errors.py::test_passes_with_warnings': ['WARNING', 'PASSED'],
        
        # Tests with errors
        'demo-tests/test_1.py::test_14_causes_error_pass_stderr_stdout_stdlog': ['ERROR'],
        'demo-tests/test_1.py::test_15_causes_error_fail_stderr_stdout_stdlog': ['ERROR'],
        'demo-tests/test_2.py::test_c_error': ['ERROR'],
        'demo-tests/test_issue_1004.py::test_foo': ['ERROR', 'PASSED'],
        'demo-tests/test_issue_1004.py::test_foo2': ['ERROR', 'FAILED'],
        
        # Regular tests
        'demo-tests/test_1.py::test_a_ok': ['PASSED'],
        'demo-tests/test_1.py::test_b_fail': ['FAILED'],
        'demo-tests/test_1.py::test_c_error': ['ERROR', 'PASSED'],
        'demo-tests/test_1.py::test_d1_skip_inline': ['SKIPPED'],
    }


def generate_test_results(session_id: int, num_tests: int, base_time: datetime) -> list:
    """Generate test results for a session."""
    templates = get_test_templates()
    test_ids = list(templates.keys())
    
    # Select a random subset of tests
    selected_tests = random.sample(test_ids, min(num_tests, len(test_ids)))
    
    # Generate results
    results = []
    for test_id in selected_tests:
        possible_outcomes = templates[test_id]
        outcome = random.choice(possible_outcomes)
        
        # Add some variance to the timestamp
        timestamp = base_time + timedelta(seconds=random.uniform(0, 300))
        
        result = {
            'session_id': session_id,
            'test_id': test_id,
            'outcome': outcome,
            'timestamp': timestamp,
            'duration': random.uniform(0.1, 2.0),
            'error_message': 'Error occurred' if outcome in ['ERROR', 'FAILED'] else None,
            'error_type': 'AssertionError' if outcome == 'FAILED' else 'RuntimeError' if outcome == 'ERROR' else None,
            'has_warning': random.random() < 0.2,  # 20% chance of having a warning
        }
        results.append(result)
    
    return results


def create_template_session():
    """Create a template test session."""
    return {
        'session_id': str(uuid.uuid4()),
        'start_time': datetime.now(),
        'end_time': datetime.now() + timedelta(minutes=5),
        'duration': 300.0,  # 5 minutes
        'sut_id': random.choice(SUT_IDS),
        'sut_type': 'local',
        'sut_version': '1.0.0',
        'sut_env': 'test',
        'num_tests': 18,  # Number of tests in our template
        'num_passes': 10,
        'num_failures': 3,
        'num_errors': 2,
        'num_skips': 1,
        'num_xfails': 1,
        'num_xpasses': 1
    }


def ensure_template_data():
    """Ensure there is at least one template session in the database."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if we have any sessions
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
                num_errors, num_skips, num_xfails, num_xpasses
            ) VALUES (
                :session_id, :start_time, :end_time, :duration,
                :sut_id, :sut_type, :sut_version, :sut_env,
                :num_tests, :num_passes, :num_failures,
                :num_errors, :num_skips, :num_xfails, :num_xpasses
            )
            """,
            template
        )
        
        # Get the session ID
        session_id = cursor.lastrowid
        
        # Generate test results for the template
        test_results = generate_test_results(
            session_id=session_id,
            num_tests=template['num_tests'],
            base_time=template['start_time']
        )
        
        # Insert test results
        for result in test_results:
            cursor.execute(
                """
                INSERT INTO test_results (
                    session_id, test_id, outcome, timestamp,
                    duration, error_message, error_type, has_warning
                ) VALUES (
                    :session_id, :test_id, :outcome, :timestamp,
                    :duration, :error_message, :error_type, :has_warning
                )
                """,
                result
            )
        
        conn.commit()
        print(f"Created template session with {len(test_results)} test results")
    
    conn.close()


def generate_historical_data(days: int = 7, sessions_per_day: tuple = (3, 8)):
    """Generate historical test data."""
    db_path = get_db_path()

    # Ensure we have template data
    ensure_template_data()

    # Connect to database
    conn = sqlite3.connect(db_path)

    # Get existing sessions as templates
    query = """
        SELECT
            session_id, start_time, end_time, duration,
            sut_id, sut_type, sut_version, sut_env,
            num_tests, num_passes, num_failures,
            num_errors, num_skips, num_xfails, num_xpasses
        FROM test_sessions
        ORDER BY start_time DESC
        LIMIT 10
    """
    print(f"Executing query: {query}")
    df = pd.read_sql_query(query, conn)

    print(f"Found {len(df)} template sessions")
    if len(df) == 0:
        print("No existing test sessions found to use as templates!")
        return

    print("\nTemplate session columns:")
    print(df.columns.tolist())

    template_sessions = df.to_dict("records")

    # Generate historical data
    new_sessions = []
    all_test_results = []
    current_time = datetime.now()

    for day in range(days):
        # Calculate base time for this day
        base_time = current_time - timedelta(days=day)
        day_start = base_time.replace(hour=9, minute=0, second=0, microsecond=0)

        # Generate random number of sessions for this day
        num_sessions = random.randint(sessions_per_day[0], sessions_per_day[1])

        for session in range(num_sessions):
            # Pick a random template session
            template = random.choice(template_sessions)

            # Calculate time for this session
            session_time = day_start + timedelta(
                hours=random.uniform(0, 8), minutes=random.uniform(0, 60)
            )

            # Create varied version
            varied_session = vary_session(template, session_time)
            new_sessions.append(varied_session)

    # Sort by timestamp
    new_sessions.sort(key=lambda x: x["start_time"])

    print(f"\nInserting {len(new_sessions)} new sessions...")

    # Insert new sessions and generate test results
    cursor = conn.cursor()

    for session in new_sessions:
        # Insert session
        cursor.execute(
            """
            INSERT INTO test_sessions (
                session_id, start_time, end_time, duration,
                sut_id, sut_type, sut_version, sut_env,
                num_tests, num_passes, num_failures,
                num_errors, num_skips, num_xfails, num_xpasses
            ) VALUES (
                :session_id, :start_time, :end_time, :duration,
                :sut_id, :sut_type, :sut_version, :sut_env,
                :num_tests, :num_passes, :num_failures,
                :num_errors, :num_skips, :num_xfails, :num_xpasses
            )
        """,
            session,
        )
        
        # Get the session ID (SQLite's last_insert_rowid)
        session_id = cursor.lastrowid
        
        # Generate and collect test results
        test_results = generate_test_results(
            session_id=session_id,
            num_tests=session['num_tests'],
            base_time=session['start_time']
        )
        all_test_results.extend(test_results)

    # Insert all test results
    print(f"\nInserting {len(all_test_results)} test results...")
    for result in all_test_results:
        cursor.execute(
            """
            INSERT INTO test_results (
                session_id, test_id, outcome, timestamp,
                duration, error_message, error_type, has_warning
            ) VALUES (
                :session_id, :test_id, :outcome, :timestamp,
                :duration, :error_message, :error_type, :has_warning
            )
        """,
            result,
        )

    conn.commit()
    conn.close()

    print(
        f"\nSuccessfully generated {len(new_sessions)} historical test sessions "
        f"with {len(all_test_results)} test results over {days} days"
    )


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
    print(f"Database purged. Remaining sessions: {sessions_count}, remaining results: {results_count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate historical test data")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to generate data for",
    )
    parser.add_argument(
        "--min-sessions",
        type=int,
        default=3,
        help="Minimum number of sessions per day",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=8,
        help="Maximum number of sessions per day",
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
