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


def vary_session(session: Dict[Any, Any], base_time: datetime) -> Dict[Any, Any]:
    """Create a varied version of a test session."""
    varied = session.copy()

    # Generate new session ID
    varied["session_id"] = str(uuid.uuid4())

    # Print debug info
    print("\nTemplate session values:")
    for k, v in varied.items():
        print(f"{k}: {v}")

    # Vary the test counts (maintain consistency)
    total = int(varied["num_tests"] or 0)  # Handle NULL
    passed = int(varied["num_passes"] or 0)
    failed = int(varied["num_failures"] or 0)
    errors = int(varied["num_errors"] or 0)
    skipped = int(varied["num_skips"] or 0)

    # Calculate new counts while maintaining reasonable proportions
    new_total = vary_number(total, 0.1)
    ratio = new_total / total if total > 0 else 1

    new_passed = int(passed * ratio * random.uniform(0.95, 1.05))
    new_failed = int(failed * ratio * random.uniform(0.9, 1.1))
    new_errors = int(errors * ratio * random.uniform(0.9, 1.1))
    new_skipped = int(skipped * ratio * random.uniform(0.9, 1.1))

    # Ensure totals add up
    while (new_passed + new_failed + new_errors + new_skipped) != new_total:
        diff = new_total - (new_passed + new_failed + new_errors + new_skipped)
        if diff > 0:
            new_passed += diff
        else:
            new_passed = max(0, new_passed + diff)

    varied["num_tests"] = new_total
    varied["num_passes"] = new_passed
    varied["num_failures"] = new_failed
    varied["num_errors"] = new_errors
    varied["num_skips"] = new_skipped

    # Vary the duration (handle NULL values)
    base_duration = float(varied["duration"] or 10.0)  # Default to 10 seconds if NULL
    varied["duration"] = base_duration * random.uniform(0.9, 1.1)

    # Set the timestamps
    varied["start_time"] = base_time
    varied["end_time"] = base_time + timedelta(seconds=varied["duration"])

    # Handle potentially NULL fields
    varied["sut_id"] = varied["sut_id"] or ""
    varied["sut_type"] = varied["sut_type"] or ""
    varied["sut_version"] = varied["sut_version"] or ""
    varied["sut_env"] = varied["sut_env"] or ""

    return varied


def generate_historical_data(days: int = 7, sessions_per_day: tuple = (3, 8)):
    """Generate historical test data."""
    db_path = get_db_path()

    # Connect to database
    conn = sqlite3.connect(db_path)

    # Get existing sessions as templates
    query = """
        SELECT
            session_id, start_time, end_time, duration,
            sut_id, sut_type, sut_version, sut_env,
            num_tests, num_passes, num_failures,
            num_errors, num_skips
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

    # Insert new sessions
    cursor = conn.cursor()

    for session in new_sessions:
        cursor.execute(
            """
            INSERT INTO test_sessions (
                session_id, start_time, end_time, duration,
                sut_id, sut_type, sut_version, sut_env,
                num_tests, num_passes, num_failures,
                num_errors, num_skips
            ) VALUES (
                :session_id, :start_time, :end_time, :duration,
                :sut_id, :sut_type, :sut_version, :sut_env,
                :num_tests, :num_passes, :num_failures,
                :num_errors, :num_skips
            )
        """,
            session,
        )

    conn.commit()
    conn.close()

    print(
        f"\nSuccessfully generated {len(new_sessions)} historical test sessions over {days} days"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate historical test data")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days of historical data to generate",
    )
    parser.add_argument(
        "--min-sessions", type=int, default=3, help="Minimum sessions per day"
    )
    parser.add_argument(
        "--max-sessions", type=int, default=8, help="Maximum sessions per day"
    )

    args = parser.parse_args()

    generate_historical_data(
        days=args.days, sessions_per_day=(args.min_sessions, args.max_sessions)
    )
