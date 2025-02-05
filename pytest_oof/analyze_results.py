#!/usr/bin/env python3

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
from click import Context

from pytest_oof.db import (
    db_connection,
    delete_results,
    export_results,
    get_db_id_from_session_id,
    init_db,
)
from pytest_oof.utils import LongitudinalAnalysis, Results, TestHistory


def validate_timestamp(
    ctx: Context, param: click.Parameter, value: str
) -> Optional[datetime]:
    """Convert ISO timestamp string to datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise click.BadParameter(
            "Timestamp must be in ISO format (e.g. 2025-02-04T12:00:00)"
        )


def list_recent_sessions(db_path: Path, limit: int = 10) -> List[Dict[str, Any]]:
    """List recent test sessions."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, session_id, start_time, end_time, duration, sut_id, sut_type
            FROM test_sessions
            ORDER BY start_time DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = [desc[0] for desc in c.description]
        return [dict(zip(columns, row)) for row in c.fetchall()]


def get_short_session_id(session_id: str, length: int = 8) -> str:
    """Get a shortened version of the session ID."""
    return session_id[
        -length:
    ]  # Use last 8 chars since they contain the unique random part


def find_session_by_suffix(db_path: Path, suffix: str) -> Optional[str]:
    """Find a full session ID given a suffix."""
    with db_connection(db_path) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT session_id FROM test_sessions WHERE session_id LIKE ?",
            (f"%{suffix}",),
        )
        matches = c.fetchall()
        if not matches:
            return None
        if len(matches) > 1:
            # If multiple matches, list them all
            click.echo(f"\nMultiple sessions found ending with '{suffix}':")
            for match in matches:
                click.echo(f"- {match[0]}")
            return None
        return matches[0][0]


def analyze_results(
    db_path: Path,
    sut_id: str = "",
    sut_type: str = "",
    sut_version: str = "",
    sut_env: str = "",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    last_n_sessions: Optional[int] = None,
    outcome: Optional[str] = None,
    test_id: Optional[str] = None,
    compare_sessions: Optional[Tuple[str, ...]] = None,
    export_file: Optional[Path] = None,
    session_id: Optional[str] = None,
    list_sessions: bool = False,
    list_sessions_limit: int = 10,
    compare_with: Optional[str] = None,
    output_format: str = "json",  # Add output_format parameter with default value
) -> None:
    """Analyze test results from the database."""
    # Initialize database if it doesn't exist
    init_db(db_path)

    # If --list-sessions is specified, show recent sessions
    if list_sessions:
        sessions = list_recent_sessions(db_path, list_sessions_limit)
        if not sessions:
            click.echo("No test sessions found.")
            return

        click.echo("\nRecent test sessions:")
        for session in sessions:
            session_id = session["session_id"]
            short_id = get_short_session_id(session_id)
            start_time = session["start_time"]
            sut_info = f" ({session['sut_id']})" if session["sut_id"] else ""
            click.echo(
                f"- {short_id}: {start_time}{sut_info}"
            )
        return

    # If export file is specified, export results
    if export_file:
        click.echo(f"\nExporting results to {export_file}...")
        export_results(
            db_path,
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            sut_id=sut_id,
            sut_type=sut_type,
            sut_version=sut_version,
            sut_env=sut_env,
            output_file=export_file,
            output_format=output_format,  # Pass output_format to export_results
            outcome=outcome,
            test_id=test_id,
        )
        click.echo("Export complete.")
        return

    # Convert outcome to lowercase
    if outcome is not None:
        outcome = outcome.lower()

    # If a session ID is provided, find its database ID
    db_id = None
    if session_id is not None:
        # First try to find by exact match
        with db_connection(db_path) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id FROM test_sessions WHERE session_id = ?",
                (session_id,),
            )
            result = c.fetchone()

            # If no exact match, try to find by suffix
            if not result:
                full_session_id = find_session_by_suffix(db_path, session_id)
                if not full_session_id:
                    if full_session_id is None:
                        # Multiple matches were found and already displayed
                        return
                    click.echo(f"No session found with session ID {session_id}")
                    return
                c.execute(
                    "SELECT id FROM test_sessions WHERE session_id = ?",
                    (full_session_id,),
                )
                result = c.fetchone()

            db_id = result[0]

    # If a specific session ID is provided, show detailed results for that session
    if db_id is not None:
        results = export_results(
            db_path=db_path, session_id=db_id, output_format="json"
        )
        if not results:
            click.echo(f"No results found for session ID {session_id}")
            return

        result = results[0]  # Get the first (and only) result
        session = result["session"]  # Get the session data from the nested structure
        test_results = result.get("test_results", [])  # Get test results safely

        # Get the last 6 characters of the session ID for display
        display_id = session.get("session_id", "N/A")
        if len(display_id) > 6:
            display_id = display_id[-6:]

        click.echo(f"\nSession {display_id} Details:")
        click.echo("-" * 40)
        # Safely access dictionary keys
        click.echo(f"Session ID: {session.get('session_id', 'N/A')}")
        click.echo(f"Start Time: {session.get('start_time', 'N/A')}")
        click.echo(f"End Time: {session.get('end_time', 'N/A') or 'N/A'}")
        duration = session.get("duration")
        if duration is not None:
            click.echo(f"Duration: {duration:.2f} seconds")
        else:
            click.echo("Duration: N/A")

        # Show test statistics if available
        if session.get("num_tests"):
            click.echo(f"\nTest Statistics:")
            click.echo(f"Total Tests: {session.get('num_tests', 0)}")
            click.echo(f"Passed: {session.get('num_passes', 0)}")
            click.echo(f"Failed: {session.get('num_failures', 0)}")
            click.echo(f"Errors: {session.get('num_errors', 0)}")
            click.echo(f"Skipped: {session.get('num_skips', 0)}")
            if session.get("num_xfails", 0) > 0:
                click.echo(f"XFails: {session.get('num_xfails')}")
            if session.get("num_xpasses", 0) > 0:
                click.echo(f"XPasses: {session.get('num_xpasses')}")
            if session.get("num_reruns", 0) > 0:
                click.echo(f"Reruns: {session.get('num_reruns')}")
            if session.get("num_warnings", 0) > 0:
                click.echo(f"Warnings: {session.get('num_warnings')}")
            if session.get("num_deselected", 0) > 0:
                click.echo(f"Deselected: {session.get('num_deselected')}")

        # Show SUT info if available
        if any(
            session.get(k) for k in ["sut_id", "sut_type", "sut_version", "sut_env"]
        ):
            click.echo("\nSUT Information:")
            if session.get("sut_id"):
                click.echo(f"SUT ID: {session['sut_id']}")
            if session.get("sut_type"):
                click.echo(f"SUT Type: {session['sut_type']}")
            if session.get("sut_version"):
                click.echo(f"SUT Version: {session['sut_version']}")
            if session.get("sut_env"):
                click.echo(f"SUT Environment: {session['sut_env']}")

        # Show environment info if available
        if any(session.get(k) for k in ["python_version", "pytest_version", "os_info"]):
            click.echo("\nEnvironment Information:")
            if session.get("python_version"):
                click.echo(f"Python Version: {session['python_version']}")
            if session.get("pytest_version"):
                click.echo(f"Pytest Version: {session['pytest_version']}")
            if session.get("os_info"):
                click.echo(f"OS Info: {session['os_info']}")

        click.echo("\nTest Results:")
        click.echo("-" * 40)
        if not test_results:
            click.echo("No test results found")
        else:
            # Count test outcomes
            outcomes = {"PASSED": 0, "FAILED": 0, "ERROR": 0, "SKIPPED": 0}
            for test in test_results:
                outcome = test.get("outcome", "UNKNOWN")
                if outcome in outcomes:
                    outcomes[outcome] += 1

            # Display summary
            for outcome, count in outcomes.items():
                if count > 0:
                    click.echo(f"{outcome}: {count}")

            click.echo("\nFailed Tests:")
            click.echo("-" * 40)
            failed_tests = [
                t for t in test_results if t.get("outcome") in ("FAILED", "ERROR")
            ]
            if not failed_tests:
                # Only show "No failed tests" if we have test results but none failed
                click.echo("No failed tests")
            else:
                for test in failed_tests:
                    test_id = test.get("test_id", "Unknown test")
                    outcome = test.get("outcome", "UNKNOWN")
                    error_type = test.get("error_type", "Unknown error")
                    error_message = test.get("error_message", "No error message")
                    click.echo(f"{test_id}: {outcome}")
                    if error_type != "Unknown error":
                        click.echo(f"  Error Type: {error_type}")
                    if error_message != "No error message":
                        click.echo(f"  Error Message: {error_message}")
                    if test.get("longreprtext"):
                        click.echo("  Details:")
                        for line in test["longreprtext"].splitlines()[
                            :5
                        ]:  # Show first 5 lines
                            click.echo(f"    {line}")
                        if len(test["longreprtext"].splitlines()) > 5:
                            click.echo("    ...")

        return

    # Export results if requested
    if export_file:
        results = export_results(
            db_path=db_path,
            sut_id=sut_id or None,
            sut_type=sut_type or None,
            sut_version=sut_version or None,
            sut_env=sut_env or None,
            start_time=start_time,
            end_time=end_time,
            outcome=outcome,
            test_id=test_id,
            output_file=export_file,
            output_format="jsonl" if export_file.suffix == ".jsonl" else "json",
        )
        if not results:
            click.echo("No results found matching the specified criteria")
            return

    # Load test history
    history = TestHistory()
    history.path = db_path
    history.load_test_results(
        sut_id=sut_id or None,
        sut_type=sut_type or None,
        sut_version=sut_version or None,
        sut_env=sut_env or None,
        start_time=start_time,
        end_time=end_time,
        last_n_sessions=last_n_sessions,
        outcome=outcome,
        test_id=test_id,
    )

    # Print summary stats
    click.echo("\nSummary Statistics:")
    click.echo("-" * 40)
    click.echo(f"Total Sessions: {len(history.test_sessions)}")
    click.echo(f"Total Tests: {history.total_tests}")
    click.echo(f"Total Passes: {history.total_passes} ({history.pass_rate:.1%})")
    click.echo(f"Total Failures: {history.total_failures} ({history.failure_rate:.1%})")
    click.echo(f"Total Errors: {history.total_errors} ({history.error_rate:.1%})")
    click.echo(f"Total Skips: {history.total_skips} ({history.skip_rate:.1%})")
    click.echo(f"Expected Failures: {history.total_xfails} ({history.xfail_rate:.1%})")
    click.echo(f"Unexpected Passes: {history.total_xpasses} ({history.xpass_rate:.1%})")
    click.echo(f"Total Reruns: {history.total_reruns}")

    # Print most recent changes
    click.echo("\nMost Recent Changes:")
    click.echo("-" * 40)
    changes = history.find_test_changes()
    if changes["new_failures"]:
        click.echo("\nNew Failures:")
        for test in changes["new_failures"]:
            click.echo(f"  - {test}")
    if changes["new_passes"]:
        click.echo("\nNew Passes:")
        for test in changes["new_passes"]:
            click.echo(f"  - {test}")
    if changes["intermittent"]:
        click.echo("\nIntermittent Tests:")
        for test in changes["intermittent"]:
            click.echo(f"  - {test}")

    # Print trend analysis
    click.echo("\nTrend Analysis:")
    click.echo("-" * 40)
    analysis = LongitudinalAnalysis(history.test_sessions)
    trend_stats = analysis.get_trend_stats()
    for window in trend_stats:
        click.echo(f"\nWindow {window['window_start']} to {window['window_end']}:")
        click.echo(f"  Tests: {window['num_tests']}")
        click.echo(f"  Passes: {window['num_passes']}")
        click.echo(f"  Failures: {window['num_failures']}")
        click.echo(f"  Errors: {window['num_errors']}")
        click.echo(f"  Skips: {window['num_skips']}")
        click.echo(f"  Expected Failures: {window['num_xfails']}")
        click.echo(f"  Unexpected Passes: {window['num_xpasses']}")
        click.echo(f"  Reruns: {window['num_reruns']}")

    # Handle session comparison
    if compare_with:
        # Get the database IDs for both sessions
        db_id1 = get_db_id_from_session_id(db_path, session_id)
        db_id2 = get_db_id_from_session_id(db_path, compare_with)
        if not db_id1:
            click.echo(f"Session {session_id} not found")
            return
        if not db_id2:
            click.echo(f"Session {compare_with} not found")
            return

        # Get results for both sessions
        results1 = export_results(
            db_path=db_path, session_id=db_id1, output_format="json"
        )
        results2 = export_results(
            db_path=db_path, session_id=db_id2, output_format="json"
        )
        if not results1 or not results2:
            click.echo("Could not retrieve session data")
            return

        session1 = results1[0]["session"]
        session2 = results2[0]["session"]
        test_results1 = results1[0].get("test_results", [])
        test_results2 = results2[0].get("test_results", [])

        # Display comparison
        click.echo("\nSession Comparison:")
        click.echo("-" * 80)
        click.echo(f"{'Field':<20} {'Session 1':<30} {'Session 2':<30}")
        click.echo("-" * 80)

        # Compare basic session info
        fields = [
            ("Session ID", "session_id"),
            ("Start Time", "start_time"),
            ("End Time", "end_time"),
            ("Duration", "duration"),
        ]
        for label, field in fields:
            val1 = session1.get(field, "N/A")
            val2 = session2.get(field, "N/A")
            if field == "session_id" and len(str(val1)) > 6:
                val1 = f"{str(val1)[-6:]} ({val1})"
            if field == "session_id" and len(str(val2)) > 6:
                val2 = f"{str(val2)[-6:]} ({val2})"
            if field == "duration" and val1 != "N/A":
                val1 = f"{val1:.2f}s"
            if field == "duration" and val2 != "N/A":
                val2 = f"{val2:.2f}s"
            click.echo(f"{label:<20} {str(val1):<30} {str(val2):<30}")

        # Compare test statistics
        click.echo("\nTest Statistics:")
        click.echo("-" * 80)
        stats_fields = [
            ("Total Tests", "num_tests"),
            ("Passed", "num_passes"),
            ("Failed", "num_failures"),
            ("Errors", "num_errors"),
            ("Skipped", "num_skips"),
            ("XFails", "num_xfails"),
            ("XPasses", "num_xpasses"),
        ]
        for label, field in stats_fields:
            val1 = session1.get(field, 0)
            val2 = session2.get(field, 0)
            diff = val2 - val1
            diff_str = ""
            if diff != 0:
                diff_str = f"({'+' if diff > 0 else ''}{diff})"
            click.echo(f"{label:<20} {val1:<15} {val2:<15} {diff_str}")

        # Compare failed tests
        click.echo("\nFailed Tests Comparison:")
        click.echo("-" * 80)
        failed_tests1 = {
            t["test_id"]: t
            for t in test_results1
            if t.get("outcome") in ("FAILED", "ERROR")
        }
        failed_tests2 = {
            t["test_id"]: t
            for t in test_results2
            if t.get("outcome") in ("FAILED", "ERROR")
        }

        # Tests that failed in both sessions
        common_failures = set(failed_tests1.keys()) & set(failed_tests2.keys())
        if common_failures:
            click.echo("\nTests failing in both sessions:")
            for test_id in sorted(common_failures):
                click.echo(f"  {test_id}")

        # Tests that failed only in session 1
        only_in_1 = set(failed_tests1.keys()) - set(failed_tests2.keys())
        if only_in_1:
            click.echo(f"\nTests failing only in session {session_id[-6:]}:")
            for test_id in sorted(only_in_1):
                click.echo(f"  {test_id}")

        # Tests that failed only in session 2
        only_in_2 = set(failed_tests2.keys()) - set(failed_tests1.keys())
        if only_in_2:
            click.echo(f"\nTests failing only in session {compare_with[-6:]}:")
            for test_id in sorted(only_in_2):
                click.echo(f"  {test_id}")

        return


@click.command()
@click.argument(
    "db_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("test_results.db"),
)
@click.option("--delete-all", is_flag=True, help="Delete all test results")
@click.option("--delete-last-n", type=int, help="Delete the last N sessions")
@click.option(
    "--delete-after",
    help="Delete sessions after this time (YYYY-MM-DD[THH:MM:SS])",
)
@click.option(
    "--delete-before",
    help="Delete sessions before this time (YYYY-MM-DD[THH:MM:SS])",
)
@click.option("--delete-sut-id", help="Delete sessions for a specific SUT ID")
@click.option("--list-sessions", is_flag=True, help="List recent test sessions")
@click.option(
    "--list-sessions-limit",
    type=int,
    default=10,
    help="Number of sessions to list (default: 10)",
)
@click.option("--id", help="Show details for a specific session ID")
@click.option(
    "--export",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Export results to file",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "jsonl"]),
    default="json",
    help="Output format for export (default: json)",
)
@click.option("--after", help="Filter by start time (YYYY-MM-DD[THH:MM:SS])")
@click.option("--before", help="Filter by end time (YYYY-MM-DD[THH:MM:SS])")
@click.option("--sut-id", help="Filter by SUT ID")
@click.option("--sut-type", help="Filter by SUT type")
@click.option("--outcome", help="Filter by test outcome")
@click.option("--test-id", help="Filter by test ID")
@click.option(
    "--compare",
    nargs=2,
    help="Compare two sessions by their IDs (short or full)",
)
def main(
    db_path: Path,
    delete_all: bool,
    delete_last_n: Optional[int],
    delete_after: Optional[str],
    delete_before: Optional[str],
    delete_sut_id: Optional[str],
    list_sessions: bool,
    list_sessions_limit: int,
    id: Optional[str],
    export: Optional[Path],
    output_format: str,
    after: Optional[str],
    before: Optional[str],
    sut_id: Optional[str],
    sut_type: Optional[str],
    outcome: Optional[str],
    test_id: Optional[str],
    compare: Optional[Tuple[str, str]],
) -> None:
    """Analyze and manage test results from the database.

    This tool allows you to analyze test results, compare sessions, and manage the test history database.
    You can filter results by various criteria, export data to files, and perform cleanup operations.
    """
    # Initialize database if it doesn't exist
    init_db(db_path)

    # Handle deletion commands first
    if delete_all:
        num_deleted = delete_results(db_path, all_results=True)
        click.echo(f"Deleted {num_deleted} test sessions")
        return

    if delete_last_n:
        num_deleted = delete_results(db_path, last_n_sessions=delete_last_n)
        click.echo(f"Deleted {num_deleted} test sessions")
        return

    if delete_after or delete_before:
        try:
            after_time = datetime.fromisoformat(delete_after) if delete_after else None
            before_time = (
                datetime.fromisoformat(delete_before) if delete_before else None
            )
        except ValueError:
            click.echo(
                "Timestamp must be in ISO format (e.g. 2025-02-04T12:00:00)",
                err=True,
            )
            return
        num_deleted = delete_results(
            db_path, start_time=after_time, end_time=before_time
        )
        click.echo(f"Deleted {num_deleted} test sessions")
        return

    if delete_sut_id:
        num_deleted = delete_results(db_path, sut_id=delete_sut_id)
        click.echo(f"Deleted {num_deleted} test sessions")
        return

    # Handle analysis commands
    try:
        start_dt = datetime.fromisoformat(after) if after else None
        end_dt = datetime.fromisoformat(before) if before else None
    except ValueError:
        click.echo(
            "Timestamp must be in ISO format (e.g. 2025-02-04T12:00:00)",
            err=True,
        )
        return

    # Compare two sessions if requested
    if compare:
        session_id1, session_id2 = compare
        analyze_results(
            db_path=db_path,
            session_id=session_id1,
            export_file=export,
            output_format=output_format,
            compare_with=session_id2,
        )
        return

    # Show details for a specific session
    if id:
        analyze_results(
            db_path=db_path,
            session_id=id,
            export_file=export,
            output_format=output_format,
        )
        return

    # List sessions if requested
    if list_sessions:
        analyze_results(
            db_path=db_path,
            list_sessions=True,
            list_sessions_limit=list_sessions_limit,
        )
        return

    # Export results with filters
    analyze_results(
        db_path=db_path,
        start_time=start_dt,
        end_time=end_dt,
        sut_id=sut_id,
        sut_type=sut_type,
        outcome=outcome,
        test_id=test_id,
        export_file=export,
        output_format=output_format,
    )


if __name__ == "__main__":
    main()
