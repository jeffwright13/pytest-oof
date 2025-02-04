#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from typing import Optional
import sys

from pytest_oof.utils import TestHistory, LongitudinalAnalysis, Results, SessionMetadata, TestResult, TestSessionStats, ReportBasedStats, OutputFields, OutputField, RerunTestGroup

def parse_datetime(s: str) -> datetime:
    """Parse datetime string in ISO format with optional timezone."""
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

def dict_to_results(data: dict) -> Results:
    """Convert a dictionary back into a Results object."""
    # Convert session metadata
    session_metadata = SessionMetadata(
        session_id=data["session_metadata"]["session_id"],
        start_time=datetime.fromisoformat(data["session_metadata"]["start_time"]),
        stop_time=datetime.fromisoformat(data["session_metadata"].get("stop_time", data["session_metadata"]["start_time"])),
        duration=timedelta(seconds=data["session_metadata"]["duration"]),
        sut_id=data["session_metadata"].get("sut_id", ""),
        sut_type=data["session_metadata"].get("sut_type", ""),
        sut_version=data["session_metadata"].get("sut_version", ""),
        sut_environment=data["session_metadata"].get("sut_environment", ""),
        sut_metadata=data["session_metadata"].get("sut_metadata", {})
    )
    
    # Convert test results
    test_results = []
    for tr in data["test_results"]:
        test_result = TestResult(
            nodeid=tr["nodeid"],
            outcome=tr["outcome"],
            start_time=datetime.fromisoformat(tr["start_time"]) if tr.get("start_time") else None,
            duration=tr.get("duration", 0.0),
            has_warning=tr.get("has_warning", False),
            caplog=tr.get("caplog", ""),
            capstderr=tr.get("capstderr", ""),
            capstdout=tr.get("capstdout", ""),
            longreprtext=tr.get("longreprtext", ""),
            longreprtext_stripped=tr.get("longreprtext_stripped", ""),
        )
        test_results.append(test_result)
    
    # Convert stats
    session_stats = TestSessionStats(**data["session_stats"]) if data.get("session_stats") else None
    report_stats = ReportBasedStats(**data["report_stats"]) if data.get("report_stats") else None
    
    # Create output fields
    output_fields = OutputFields()
    if data.get("output_fields"):
        for field_name, field_data in data["output_fields"].items():
            if hasattr(output_fields, field_name):
                field = OutputField(
                    name=field_data.get("name", ""),
                    content=field_data.get("content", ""),
                    content_stripped=field_data.get("content_stripped", "")
                )
                setattr(output_fields, field_name, field)
    
    # Convert warnings and rerun groups
    warnings = [TestResult(**w) for w in data.get("warnings", [])]
    rerun_groups = []
    for rg in data.get("rerun_test_groups", []):
        group = RerunTestGroup(
            nodeid=rg["nodeid"],
            final_outcome=rg["final_outcome"],
            final_test=TestResult(**rg["final_test"]) if rg.get("final_test") else None,
            forerunners=[TestResult(**t) for t in rg.get("forerunners", [])],
        )
        rerun_groups.append(group)
    
    return Results(
        session_metadata=session_metadata,
        session_stats=session_stats,
        report_stats=report_stats,
        test_results=test_results,
        output_fields=output_fields,
        warnings=warnings,
        rerun_test_groups=rerun_groups
    )

def analyze_results(
    json_file: Path,
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
):
    """Analyze test results using various methods."""
    
    # Check if file exists
    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        return
        
    # Check if file is empty
    if json_file.stat().st_size == 0:
        print(f"Error: File is empty: {json_file}")
        return
    
    try:
        # Load JSON history
        with open(json_file) as f:
            results_history = json.load(f)
        
        if not isinstance(results_history, list):
            print(f"Error: Expected a list of results in {json_file}, but got {type(results_history).__name__}. The file may be corrupted.")
            return
            
        if not results_history:
            print(f"No test results found in {json_file}")
            return
        
        # Convert JSON results to Results objects
        history = TestHistory()
        for result_data in results_history:
            try:
                history.add_run(dict_to_results(result_data))
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
        
        # Parse times if provided
        try:
            start = parse_datetime(start_time) if start_time else None
            end = parse_datetime(end_time) if end_time else None
        except ValueError as e:
            print(f"Error: Invalid date format: {e}")
            print("Please use ISO format (YYYY-MM-DDTHH:MM:SS+HH:MM) or YYYY-MM-DD")
            return
        
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
                
                for change in sorted(history, key=lambda x: x['time']):
                    timestamp = change['time']
                    outcome = change['outcome']
                    
                    # Skip empty outcomes
                    if not outcome:
                        continue
                    
                    # Only record the change if it's different from the last outcome
                    if outcome != last_outcome:
                        if last_timestamp:
                            # Calculate time between changes
                            time_diff = timestamp - last_timestamp
                            if time_diff.total_seconds() >= min_duration_seconds:  # Use configurable minimum duration
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
                'FAILED' in pattern or 
                'ERROR' in pattern or 
                pattern[0] != pattern[-1]  # Status changed between first and last
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
            total_tests = stat['num_tests']
            pass_rate = stat['num_passes'] / total_tests if total_tests > 0 else 0
            failure_rate = (stat['num_failures'] + stat['num_errors']) / total_tests if total_tests > 0 else 0
            
            print(f"\nWindow ending {stat['window_end']}:")
            print(f"  Tests run: {total_tests}")
            print(f"  Pass rate: {pass_rate:.1%}")
            print(f"  Failure rate: {failure_rate:.1%}")
        
        # Find recent changes
        print("\n=== Recent Changes ===")
        changes = analyzer.find_test_changes(last_n_sessions=last_n_sessions)
        if changes:
            if changes.get('new_failures'):
                print("\nNew Failures:")
                for test_id in sorted(set(changes['new_failures'])):
                    print(f"  {test_id}")
            
            if changes.get('new_passes'):
                print("\nNew Passes:")
                for test_id in sorted(set(changes['new_passes'])):
                    print(f"  {test_id}")
            
            if changes.get('intermittent'):
                print("\nIntermittent Tests:")
                for test_id in sorted(set(changes['intermittent'])):
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

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {json_file}")
        return
    except Exception as e:
        print(f"Error: Failed to analyze results: {e}")
        return

def main():
    parser = argparse.ArgumentParser(description="Analyze test results")
    parser.add_argument(
        "json_file",
        type=Path,
        help="Path to oof-results.json file",
        default=Path("oof/oof-results.json"),
        nargs="?",
    )
    parser.add_argument("--sut-id", help="Filter by SUT ID")
    parser.add_argument("--sut-type", help="Filter by SUT type")
    parser.add_argument("--sut-version", help="Filter by SUT version")
    parser.add_argument("--sut-env", help="Filter by SUT environment")
    parser.add_argument("--start-time", help="Start time (ISO format or YYYY-MM-DD)")
    parser.add_argument("--end-time", help="End time (ISO format or YYYY-MM-DD)")
    parser.add_argument("--window-size", type=int, default=1, help="Window size in days for trend analysis")
    parser.add_argument("--last-n", type=int, default=1, help="Number of recent sessions to analyze")
    parser.add_argument("--min-duration", type=float, default=0, help="Minimum duration in seconds between test status changes (default: 0)")
    parser.add_argument("--show-reruns", action="store_true", help="Show rerun attempts in addition to final outcomes")
    parser.add_argument("--compare", nargs=2, metavar=("SESSION1", "SESSION2"), help="Compare two specific sessions")
    
    args = parser.parse_args()
    
    try:
        analyze_results(
            json_file=args.json_file,
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
        )
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
