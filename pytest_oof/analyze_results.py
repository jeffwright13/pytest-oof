#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pytest_oof.db import delete_results, export_results, init_db
from pytest_oof.utils import LongitudinalAnalysis, Results, TestHistory


def parse_datetime(s: str) -> datetime:
    """Parse datetime string in ISO format with optional timezone."""
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def analyze_results(
    db_path: Path,
    sut_id: str = "",
    sut_type: str = "",
    sut_version: str = "",
    sut_env: str = "",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    window_size_days: int = 1,
    last_n_sessions: int = 1,
    min_duration_seconds: float = 0,
    show_reruns: bool = False,
    compare_sessions: Optional[tuple[str, str]] = None,
    export_file: Optional[Path] = None,
):
    """Analyze test results using various methods."""

    # Check if database exists and initialize if needed
    if not db_path.exists():
        print(f"Initializing new database at: {db_path}")
        init_db(db_path)
        return

    try:
        # Parse times if provided
        try:
            start = parse_datetime(start_time) if start_time else None
            end = parse_datetime(end_time) if end_time else None
        except ValueError as e:
            print(f"Error: Invalid date format: {e}")
            print("Please use ISO format (YYYY-MM-DDTHH:MM:SS+HH:MM) or YYYY-MM-DD")
            return

        # Export results from database to Results objects
        results_data = export_results(
            db_path=db_path,
            start_time=start,
            end_time=end,
            sut_id=sut_id,
            sut_type=sut_type,
            sut_version=sut_version,
            sut_env=sut_env,
            output_file=export_file,
            output_format="jsonl" if export_file and export_file.suffix == ".jsonl" else "json",
        )

        if not results_data:
            print(f"No test results found in database {db_path}")
            return

        # Convert database results to Results objects
        history = TestHistory()
        for result_data in results_data:
            try:
                # Create a copy of the data with session_id in the expected location
                result_copy = result_data.copy()
                result_copy["session_id"] = result_copy["session"]["session_id"]
                result = Results.from_dict(result_copy)
                history.add_run(result)
            except (KeyError, ValueError) as e:
                print(f"Error: Failed to parse result data: {e}")
                return

        # Create analyzer
        analyzer = LongitudinalAnalysis(
            history=history,
            sut_id=sut_id,
            sut_type=sut_type,
            sut_version=sut_version,
            sut_environment=sut_env,
        )

        # Print SUT summary table
        print("\n=== SUT Summary ===")
        sut_stats = {}
        for result_data in results_data:
            session = result_data["session"]
            sut_id = session.get("sut_id", "unknown")
            if sut_id not in sut_stats:
                sut_stats[sut_id] = {
                    "sut_type": session.get("sut_type", "unknown"),
                    "sut_version": session.get("sut_version", "unknown"),
                    "sut_env": session.get("sut_env", "unknown"),
                    "num_sessions": 0,
                    "num_tests": 0,
                    "num_passes": 0,
                    "num_failures": 0,
                    "num_errors": 0,
                    "num_skips": 0,
                    "num_xfails": 0,
                    "num_xpasses": 0,
                    "num_reruns": 0,
                }
            stats = sut_stats[sut_id]
            stats["num_sessions"] += 1
            for test_result in result_data["test_results"]:
                stats["num_tests"] += 1
                outcome = test_result.get("outcome", "unknown").upper()
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
                elif outcome == "RERUN":
                    stats["num_reruns"] += 1

        for sut_id, stats in sorted(sut_stats.items()):
            total_tests = stats["num_tests"] or 1  # Avoid division by zero
            print(f"\nSUT ID: {sut_id}")
            print(f"  Type: {stats['sut_type']}")
            print(f"  Version: {stats['sut_version']}")
            print(f"  Environment: {stats['sut_env']}")
            print(f"  Total Sessions: {stats['num_sessions']}")
            print(f"  Total Tests: {stats['num_tests']}")
            print(f"  Passes: {stats['num_passes']} ({stats['num_passes']/total_tests:.1%})")
            print(f"  Failures: {stats['num_failures']} ({stats['num_failures']/total_tests:.1%})")
            print(f"  Errors: {stats['num_errors']} ({stats['num_errors']/total_tests:.1%})")
            print(f"  Skips: {stats['num_skips']} ({stats['num_skips']/total_tests:.1%})")
            print(f"  Expected Failures: {stats['num_xfails']} ({stats['num_xfails']/total_tests:.1%})")
            print(f"  Unexpected Passes: {stats['num_xpasses']} ({stats['num_xpasses']/total_tests:.1%})")
            print(f"  Reruns: {stats['num_reruns']} ({stats['num_reruns']/total_tests:.1%})")

        # Get test status changes
        print("\n=== Test Status Changes ===")
        changes = analyzer.get_test_status_changes(start_time=start, end_time=end)

        # Group tests by their pattern of changes
        pattern_groups = {}
        for test_id, history in changes.items():
            if len(history) > 1:  # Only process tests with multiple entries
                # Create a list of status transitions
                transitions = []
                last_outcome = None
                last_timestamp = None

                for change in sorted(history, key=lambda x: x["time"]):
                    timestamp = change["time"]
                    outcome = change["outcome"]

                    # Skip empty outcomes
                    if not outcome:
                        continue

                    # Only record the change if it's different from the last outcome
                    if outcome != last_outcome:
                        if last_timestamp:
                            # Calculate time between changes
                            time_diff = timestamp - last_timestamp
                            if (
                                time_diff.total_seconds() >= min_duration_seconds
                            ):  # Use configurable minimum duration
                                transitions.append((timestamp, outcome))
                        else:
                            transitions.append((timestamp, outcome))

                        last_outcome = outcome
                        last_timestamp = timestamp

                # Only process tests with actual transitions
                if len(transitions) > 1:
                    # Create a pattern key based on the sequence of outcomes
                    pattern = tuple(outcome for _, outcome in transitions)

                    # If not showing reruns, filter out RERUN outcomes and their associated results
                    if not show_reruns:
                        filtered_transitions = []
                        rerun_group = []
                        prev_timestamp = None

                        for timestamp, outcome in transitions:
                            if prev_timestamp and timestamp != prev_timestamp:
                                # End of a rerun group - take only the final outcome
                                if rerun_group:
                                    filtered_transitions.append(rerun_group[-1])
                                rerun_group = []

                            rerun_group.append((timestamp, outcome))
                            prev_timestamp = timestamp

                        # Handle the last group
                        if rerun_group:
                            filtered_transitions.append(rerun_group[-1])

                        # Skip if we don't have enough transitions after filtering
                        if len(filtered_transitions) < 2:
                            continue

                        # Update pattern based on filtered transitions
                        pattern = tuple(outcome for _, outcome in filtered_transitions)
                        transitions = filtered_transitions

                    if pattern not in pattern_groups:
                        pattern_groups[pattern] = []
                    pattern_groups[pattern].append((test_id, transitions))

        # Print grouped results
        for pattern, test_groups in sorted(pattern_groups.items()):
            # Only show patterns with interesting transitions
            if len(pattern) > 1 and (
                "FAILED" in pattern
                or "ERROR" in pattern
                or pattern[0] != pattern[-1]  # Status changed between first and last
            ):
                # Simplify pattern by removing consecutive duplicates
                simplified_pattern = []
                last_status = None
                for status in pattern:
                    if status != last_status:
                        simplified_pattern.append(status)
                        last_status = status

                print(f"\nTests with pattern {' -> '.join(simplified_pattern)}:")
                for test_id, transitions in sorted(test_groups):
                    print(f"\n{test_id}:")
                    for timestamp, outcome in transitions:
                        print(f"  {timestamp}: {outcome}")

        # Get trend stats
        print("\n=== Trend Statistics ===")
        stats = analyzer.get_trend_stats(window_size=timedelta(days=window_size_days))
        for stat in stats:
            total_tests = stat.get("num_tests", 0) or 1  # Use 1 if num_tests is 0 or None
            # Calculate rates for all test outcomes
            pass_rate = stat.get("num_passes", 0) / total_tests
            failure_rate = stat.get("num_failures", 0) / total_tests
            error_rate = stat.get("num_errors", 0) / total_tests
            skip_rate = stat.get("num_skips", 0) / total_tests
            xfail_rate = stat.get("num_xfails", 0) / total_tests
            xpass_rate = stat.get("num_xpasses", 0) / total_tests
            rerun_rate = stat.get("num_reruns", 0) / total_tests

            print(f"\nWindow ending {stat['window_end']}:")
            print(f"  Tests run: {total_tests}")
            print(f"  Passes: {stat.get('num_passes', 0)} ({pass_rate:.1%})")
            print(f"  Failures: {stat.get('num_failures', 0)} ({failure_rate:.1%})")
            print(f"  Errors: {stat.get('num_errors', 0)} ({error_rate:.1%})")
            print(f"  Skips: {stat.get('num_skips', 0)} ({skip_rate:.1%})")
            print(
                f"  Expected Failures (xfail): {stat.get('num_xfails', 0)} ({xfail_rate:.1%})"
            )
            print(
                f"  Unexpected Passes (xpass): {stat.get('num_xpasses', 0)} ({xpass_rate:.1%})"
            )
            print(f"  Reruns: {stat.get('num_reruns', 0)} ({rerun_rate:.1%})")

        # Find recent changes
        print("\n=== Recent Changes ===")
        changes = analyzer.find_test_changes(last_n_sessions=last_n_sessions)
        if changes:
            if changes.get("new_failures"):
                print("\nNew Failures:")
                for test_id in sorted(set(changes["new_failures"])):
                    print(f"  {test_id}")

            if changes.get("new_passes"):
                print("\nNew Passes:")
                for test_id in sorted(set(changes["new_passes"])):
                    print(f"  {test_id}")

            if changes.get("intermittent"):
                print("\nIntermittent Tests:")
                for test_id in sorted(set(changes["intermittent"])):
                    print(f"  {test_id}")
        else:
            print("No significant changes found")

        # Compare specific sessions if requested
        if compare_sessions:
            session1, session2 = compare_sessions
            print(f"\n=== Comparing Sessions {session1} vs {session2} ===")
            comparison = analyzer.compare_test_sets(session1, session2)

            if comparison["unique_to_session1"]:
                print("\nTests only in first session:")
                for test in comparison["unique_to_session1"]:
                    print(f"  {test}")

            if comparison["unique_to_session2"]:
                print("\nTests only in second session:")
                for test in comparison["unique_to_session2"]:
                    print(f"  {test}")

            print(f"\nCommon tests: {len(comparison['common_tests'])}")

    except Exception as e:
        print(f"Error: Failed to analyze results: {e}")
        return


def main():
    parser = argparse.ArgumentParser(description="Analyze test results")
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to database file (default: ./oof/oof-results.db)",
        default=Path("oof/oof-results.db"),
        nargs="?",
    )
    parser.add_argument("--sut-id", help="Filter by SUT ID")
    parser.add_argument("--sut-type", help="Filter by SUT type")
    parser.add_argument("--sut-version", help="Filter by SUT version")
    parser.add_argument("--sut-env", help="Filter by SUT environment")
    parser.add_argument("--start-time", help="Start time (ISO format or YYYY-MM-DD)")
    parser.add_argument("--end-time", help="End time (ISO format or YYYY-MM-DD)")
    parser.add_argument(
        "--window-size",
        type=int,
        default=1,
        help="Window size in days for trend analysis",
    )
    parser.add_argument(
        "--last-n", type=int, default=1, help="Number of recent sessions to analyze"
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0,
        help="Minimum duration in seconds between test status changes (default: 0)",
    )
    parser.add_argument(
        "--show-reruns",
        action="store_true",
        help="Show rerun attempts in addition to final outcomes",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("SESSION1", "SESSION2"),
        help="Compare two specific sessions",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Export results to file (use .json for JSON format or .jsonl for JSON Lines format)",
    )

    # Add delete options
    delete_group = parser.add_argument_group("delete options")
    delete_group.add_argument(
        "--delete-all",
        action="store_true",
        help="Delete all test results",
    )
    delete_group.add_argument(
        "--delete-last",
        type=int,
        metavar="N",
        help="Delete the last N test sessions",
    )
    delete_group.add_argument(
        "--delete-before",
        type=lambda s: datetime.fromisoformat(s),
        metavar="TIMESTAMP",
        help="Delete test sessions before this timestamp (ISO format)",
    )
    delete_group.add_argument(
        "--delete-after",
        type=lambda s: datetime.fromisoformat(s),
        metavar="TIMESTAMP",
        help="Delete test sessions after this timestamp (ISO format)",
    )
    delete_group.add_argument(
        "--delete-sut-id",
        help="Delete test sessions for this SUT ID",
    )
    delete_group.add_argument(
        "--delete-sut-type",
        help="Delete test sessions for this SUT type",
    )

    args = parser.parse_args()

    # Check if any delete options are specified
    delete_options = [
        args.delete_all,
        args.delete_last,
        args.delete_before,
        args.delete_after,
        args.delete_sut_id,
        args.delete_sut_type,
    ]
    if any(x is not None and x != False for x in delete_options):
        deleted = delete_results(
            db_path=args.db_path,
            all_results=args.delete_all,
            last_n_sessions=args.delete_last,
            start_time=args.delete_after,
            end_time=args.delete_before,
            sut_id=args.delete_sut_id,
            sut_type=args.delete_sut_type,
        )
        print(f"Deleted {deleted} test sessions")
        if not args.analyze:
            return

    # Continue with analysis if requested
    if args.analyze:
        analyze_results(
            db_path=args.db_path,
            sut_id=args.sut_id or "",
            sut_type=args.sut_type or "",
            sut_version=args.sut_version or "",
            sut_env=args.sut_env or "",
            start_time=args.start_time,
            end_time=args.end_time,
            window_size_days=args.window_size,
            last_n_sessions=args.last_n,
            min_duration_seconds=args.min_duration,
            show_reruns=args.show_reruns,
            compare_sessions=tuple(args.compare) if args.compare else None,
            export_file=args.export,
        )


if __name__ == "__main__":
    main()
