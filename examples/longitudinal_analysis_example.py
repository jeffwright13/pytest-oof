#!/usr/bin/env python3

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pprint import pprint

from pytest_oof.utils import (
    HISTORY_FILE,
    LongitudinalAnalysis,
    Results,
    TestHistory,
)

def main():
    """Example of using LongitudinalAnalysis to analyze test history."""
    
    # Load test history from file
    try:
        history_file = Path(HISTORY_FILE)
        history = TestHistory.load(history_file)
    except (FileNotFoundError, EOFError):
        print("No test history found. Run some tests first!")
        return

    # Create longitudinal analysis
    analysis = LongitudinalAnalysis(history)

    # 1. Get status changes for all tests in the last 7 days
    print("\n=== Test Status Changes (Last 7 Days) ===")
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    changes = analysis.get_test_status_changes(start_time=seven_days_ago)
    for nodeid, history in changes.items():
        if len(history) > 1:  # Only show tests that ran multiple times
            print(f"\nTest: {nodeid}")
            for entry in history:
                print(f"  {entry['time']}: {entry['outcome']} (duration: {entry['duration']:.2f}s)")

    # 2. Compare the two most recent test sessions
    print("\n=== Comparing Last Two Sessions ===")
    sorted_runs = sorted(history.results, key=lambda r: r.session_metadata.start_time)
    if len(sorted_runs) >= 2:
        last_session = sorted_runs[-1].session_metadata.session_id
        prev_session = sorted_runs[-2].session_metadata.session_id
        comparison = analysis.compare_test_sets(last_session, prev_session)
        
        print("\nTests added in latest session:")
        for test in comparison.get('unique_to_session1', [])[:5]:  # Show first 5
            print(f"  + {test}")
        
        print("\nTests removed in latest session:")
        for test in comparison.get('unique_to_session2', [])[:5]:  # Show first 5
            print(f"  - {test}")

    # 3. Find recent test changes
    print("\n=== Recent Test Changes ===")
    changes = analysis.find_test_changes(last_n_sessions=3)
    
    print("\nNew Failures:")
    for test in changes.get('new_failures', []):
        print(f"  ! {test}")
    
    print("\nNew Passes:")
    for test in changes.get('new_passes', []):
        print(f"  ✓ {test}")
    
    print("\nIntermittent Tests:")
    for test in changes.get('intermittent', []):
        print(f"  ~ {test}")

    # 4. Show trend statistics
    print("\n=== Trend Statistics (Daily) ===")
    trends = analysis.get_trend_stats(window_size=timedelta(days=1))
    for window in trends:
        print(f"\nWindow: {window['window_start'].date()} to {window['window_end'].date()}")
        print(f"  Sessions: {window['num_sessions']}")
        print(f"  Tests Run: {window['total_tests']}")
        print(f"  Pass Rate: {window['pass_rate']*100:.1f}%")

if __name__ == "__main__":
    main()
