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
