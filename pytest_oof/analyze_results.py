#!/usr/bin/env python3

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import click
from click import Context

from pytest_oof.db import delete_results, export_results, init_db
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
) -> None:
    """Analyze test results from the database."""
    # Initialize database if it doesn't exist
    init_db(db_path)

    # Convert outcome to lowercase
    if outcome is not None:
        outcome = outcome.lower()

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


@click.command()
@click.argument(
    "db_path",
    type=click.Path(path_type=Path),
    default=Path("oof/oof-results.db"),
    required=False,
)
@click.option(
    "--analyze/--no-analyze",
    default=True,
    help="Analyze test results",
)
@click.option(
    "--sut-id",
    help="Filter by SUT ID",
)
@click.option(
    "--sut-type",
    help="Filter by SUT type",
)
@click.option(
    "--sut-version",
    help="Filter by SUT version",
)
@click.option(
    "--sut-env",
    help="Filter by SUT environment",
)
@click.option(
    "--after",
    callback=validate_timestamp,
    help="Show results after this timestamp (ISO format)",
)
@click.option(
    "--before",
    callback=validate_timestamp,
    help="Show results before this timestamp (ISO format)",
)
@click.option(
    "--last",
    type=int,
    help="Show only the last N sessions",
)
@click.option(
    "--outcome",
    type=click.Choice(
        ["passed", "failed", "skipped", "error", "xfail", "xpass", "rerun"],
        case_sensitive=False
    ),
    help="Filter by test outcome",
)
@click.option(
    "--test-id",
    help="Filter by test ID (supports glob patterns)",
)
@click.option(
    "--compare",
    multiple=True,
    help="Compare specific test sessions by ID",
)
@click.option(
    "--export",
    type=click.Path(path_type=Path),
    help="Export results to file (.json or .jsonl)",
)
# Delete options
@click.option(
    "--delete-all",
    is_flag=True,
    help="Delete all test results",
)
@click.option(
    "--delete-last",
    type=int,
    help="Delete the last N test sessions",
)
@click.option(
    "--delete-before",
    callback=validate_timestamp,
    help="Delete test sessions before this timestamp (ISO format)",
)
@click.option(
    "--delete-after",
    callback=validate_timestamp,
    help="Delete test sessions after this timestamp (ISO format)",
)
@click.option(
    "--delete-sut-id",
    help="Delete test sessions for this SUT ID",
)
@click.option(
    "--delete-sut-type",
    help="Delete test sessions for this SUT type",
)
def main(
    db_path: Path,
    analyze: bool,
    sut_id: Optional[str],
    sut_type: Optional[str],
    sut_version: Optional[str],
    sut_env: Optional[str],
    after: Optional[datetime],
    before: Optional[datetime],
    last: Optional[int],
    outcome: Optional[str],
    test_id: Optional[str],
    compare: Tuple[str, ...],
    export: Optional[Path],
    delete_all: bool,
    delete_last: Optional[int],
    delete_before: Optional[datetime],
    delete_after: Optional[datetime],
    delete_sut_id: Optional[str],
    delete_sut_type: Optional[str],
) -> None:
    """Analyze and manage test results from the pytest-oof database.

    DB_PATH is the path to the SQLite database file (default: ./oof/oof-results.db)
    """
    # Check if any delete options are specified
    delete_options = [
        delete_all,
        delete_last,
        delete_before,
        delete_after,
        delete_sut_id,
        delete_sut_type,
    ]
    if any(x is not None and x != False for x in delete_options):
        deleted = delete_results(
            db_path=db_path,
            all_results=delete_all,
            last_n_sessions=delete_last,
            start_time=delete_after,
            end_time=delete_before,
            sut_id=delete_sut_id,
            sut_type=delete_sut_type,
        )
        click.echo(f"Deleted {deleted} test sessions")
        if not analyze:
            return

    # Convert outcome to lowercase
    if outcome is not None:
        outcome = outcome.lower()

    # Continue with analysis if requested
    if analyze:
        analyze_results(
            db_path=db_path,
            sut_id=sut_id or "",
            sut_type=sut_type or "",
            sut_version=sut_version or "",
            sut_env=sut_env or "",
            start_time=after,
            end_time=before,
            last_n_sessions=last,
            outcome=outcome,
            test_id=test_id,
            compare_sessions=compare if compare else None,
            export_file=export,
        )


if __name__ == "__main__":
    main()
