"""CLI commands for generating test data and resources."""
from datetime import datetime, timedelta

import click
from rich.console import Console

from pytest_oof.db import init_db
from pytest_oof.historical_data import generate_historical_data as gen_data
from pytest_oof.historical_data import purge_database

console = Console(width=120)

@click.group()
def generate():
    """Generate test data and resources."""
    pass

@generate.command()
@click.option(
    "--days",
    type=int,
    default=7,
    help="Number of days to generate data for (default: %(default)s)",
)
@click.option(
    "--min-sessions",
    type=int,
    default=3,
    help="Minimum number of sessions per day (default: %(default)s)",
)
@click.option(
    "--max-sessions",
    type=int,
    default=8,
    help="Maximum number of sessions per day (default: %(default)s)",
)
@click.option(
    "--include-patterns",
    is_flag=True,
    help="Include special failure patterns (global failures, flaky tests, etc.)",
)
def data(days: int, min_sessions: int, max_sessions: int, include_patterns: bool):
    """Generate historical test data.
    
    Creates test data with various patterns useful for testing and demonstration:
    
    \b
    - Global failures (all tests fail for a time window)
    - Flaky tests (alternating pass/fail patterns)
    - Version-specific failures
    - Environment-dependent failures
    - Performance trends over time
    """
    try:
        init_db()
        gen_data(
            days=days,
            sessions_per_day=(min_sessions, max_sessions),
            include_patterns=include_patterns,
        )
        console.print(
            f"[green]Successfully generated {days} days of test data "
            f"with {min_sessions}-{max_sessions} sessions per day."
        )
        if include_patterns:
            console.print(
                "\nIncluded failure patterns:"
                "\n- Global failure event (1-day window)"
                "\n- Flaky tests with varying pass/fail rates"
                "\n- Version-specific failures"
                "\n- Environment-dependent failures"
                "\n- Performance trends over time"
            )
    except Exception as e:
        console.print(f"[red]Error generating test data: {e}[/red]")

@generate.command()
def purge():
    """Purge all existing test data."""
    try:
        purge_database()
        console.print("[green]Successfully purged all test data.[/green]")
    except Exception as e:
        console.print(f"[red]Error purging test data: {e}[/red]")
