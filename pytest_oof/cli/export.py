"""CLI commands for exporting test results."""
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from pytest_oof.db import export_results

console = Console()


@click.group()
def export():
    """Export test results in various formats."""
    pass


@export.command()
@click.option(
    "--output",
    type=click.Path(),
    help="Output file path (format determined by extension: .json or .jsonl)",
)
@click.option("--sut-id", help="Filter by SUT ID")
@click.option("--sut-type", help="Filter by SUT type")
@click.option("--sut-version", help="Filter by SUT version")
@click.option("--sut-env", help="Filter by SUT environment")
@click.option(
    "--start-time",
    type=click.DateTime(),
    help="Start time for filtering (YYYY-MM-DD HH:MM:SS)",
)
@click.option(
    "--end-time",
    type=click.DateTime(),
    help="End time for filtering (YYYY-MM-DD HH:MM:SS)",
)
@click.option(
    "--outcome",
    type=click.Choice(["passed", "failed", "skipped", "xfailed", "xpassed"]),
    help="Filter by test outcome",
)
@click.option("--test-id", help="Filter by test ID")
def results(
    output: Optional[str],
    sut_id: Optional[str],
    sut_type: Optional[str],
    sut_version: Optional[str],
    sut_env: Optional[str],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    outcome: Optional[str],
    test_id: Optional[str],
):
    """Export test results to file.

    Examples:
        # Export all results to JSON
        oof export results --output results.json

        # Export recent failures for a specific SUT
        oof export results --sut-id my-service --outcome failed --output results.jsonl

        # Export results for a specific time period
        oof export results --start-time "2025-01-01 00:00:00" --end-time "2025-02-01 00:00:00"
    """
    output_path = Path(output) if output else None
    db_path = Path("./.oof/oof-results.db")  # TODO: Make this configurable

    # Determine format from file extension if output is specified
    output_format = "json"  # Default to JSON for stdout
    if output_path:
        if output_path.suffix == ".jsonl":
            output_format = "jsonl"
        elif output_path.suffix == ".json":
            output_format = "json"
        else:
            console.print(
                "[red]Error: Output file must have .json or .jsonl extension[/red]"
            )
            raise click.Abort()

    try:
        export_results(
            db_path=db_path,
            output_file=output_path,
            output_format=output_format,
            sut_id=sut_id,
            sut_type=sut_type,
            sut_version=sut_version,
            sut_env=sut_env,
            start_time=start_time,
            end_time=end_time,
            outcome=outcome,
            test_id=test_id,
        )

        if output:
            console.print(f"Results exported to [green]{output}[/green]")
        else:
            console.print(
                "[yellow]No output file specified, results will be printed to stdout[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error exporting results: {e}[/red]")
        raise click.Abort()
