"""CLI commands for generating test data and resources."""
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm

from pytest_oof.constants import get_active_db, DEFAULT_DB_PATH, TEST_DB_PATH
from pytest_oof.historical_data import purge_database

console = Console()

@click.group()
def generate():
    """Generate test data and resources."""
    pass

@generate.command()
@click.option(
    "--days",
    default=14,
    help="Number of days of historical data to generate",
)
@click.option(
    "--min-sessions",
    default=3,
    help="Minimum number of sessions per day",
)
@click.option(
    "--max-sessions",
    default=8,
    help="Maximum number of sessions per day",
)
@click.option(
    "--include-patterns/--no-include-patterns",
    default=True,
    help="Include special test failure patterns",
)
@click.option(
    "--db-path",
    type=click.Path(),
    default=None,
    help="Database to generate data in (default: current active database)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force generating data in a non-test database (USE WITH CAUTION)",
)
@click.option(
    "--purge",
    is_flag=True,
    help="Purge existing data before generating new data",
)
def data(
    days: int,
    min_sessions: int,
    max_sessions: int,
    include_patterns: bool,
    db_path: str,
    force: bool,
    purge: bool,
):
    """Generate historical test data."""
    # Logging for debugging
    console.print(f"[yellow]DEBUG: Generate data command called[/yellow]")
    console.print(f"[yellow]  days: {days}[/yellow]")
    console.print(f"[yellow]  db_path: {db_path}[/yellow]")
    console.print(f"[yellow]  force: {force}[/yellow]")
    console.print(f"[yellow]  purge: {purge}[/yellow]")

    # If no db_path provided, use the active database
    if db_path is None:
        from pytest_oof.constants import get_active_db
        db_path = str(get_active_db())

    # Validate database path
    db_path = Path(db_path)

    # Safety check for non-test databases
    if not force and not str(db_path).endswith("test-data.db"):
        console.print(
            "[red]Error: Refusing to generate test data in production database. "
            "Use --force to override.[/red]"
        )
        return

    try:
        # Set the database path for the script
        import os
        os.environ['OOF_DB_PATH'] = str(db_path)

        # Purge database if requested
        if purge:
            purge_database(db_path=str(db_path))
        else:
            from scripts.generate_historical_data import ensure_tables_exist
            ensure_tables_exist()

        # Generate new data
        from scripts.generate_historical_data import generate_historical_data
        generate_historical_data(
            days=days,
            sessions_per_day=(min_sessions, max_sessions),
            include_patterns=include_patterns,
        )

        console.print(f"[green]Successfully generated test data in {db_path}![/green]")
    except Exception as e:
        console.print(f"[red]Error generating test data: {e}[/red]")
        raise

@generate.command()
@click.option(
    "--db-path",
    type=click.Path(),
    default=None,
    help="Database to purge (default: current active database)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force purging a non-test database (USE WITH CAUTION)",
)
def purge(db_path: str = None, force: bool = False):
    """Purge all data from a database.
    
    By default, purges the current active database to avoid accidentally
    deleting real test results. Use --force to override this safety check.
    """
    # Logging for debugging
    console.print(f"[yellow]DEBUG: Purge command called[/yellow]")
    console.print(f"[yellow]  db_path: {db_path}[/yellow]")
    console.print(f"[yellow]  force: {force}[/yellow]")
    
    # If no db_path provided, use the active database
    if db_path is None:
        db_path = get_active_db()
    
    db_path = Path(db_path).resolve()
    
    # Logging resolved paths
    console.print(f"[yellow]DEBUG: Resolved paths[/yellow]")
    console.print(f"[yellow]  db_path: {db_path}[/yellow]")
    console.print(f"[yellow]  DEFAULT_DB_PATH: {DEFAULT_DB_PATH.resolve()}[/yellow]")
    
    # Safety check for production database
    if db_path == DEFAULT_DB_PATH.resolve():
        if not force:
            console.print(
                "[red]ERROR: Refusing to purge production database.[/red]\n"
                f"The specified path ({db_path}) is the production database.\n"
                "\nTo purge test data, either:\n"
                f"1. Use the default test database: --db-path {TEST_DB_PATH}\n"
                "2. Specify a different database path\n"
                "3. Use --force to override this safety check (NOT RECOMMENDED)"
            )
            return
        else:
            console.print(
                "[bright_red]CRITICAL WARNING:[/bright_red] [yellow]Forcing purge of production database![/yellow]\n"
                "[red]THIS WILL PERMANENTLY DELETE ALL DATA IN THE PRODUCTION DATABASE![/red]\n"
                f"Database path: {db_path}"
            )
    
    # Extra confirmation for any database
    if not force:
        console.print(
            "[yellow]Warning: This will permanently delete all data in:[/yellow]\n"
            f"{db_path}\n"
        )
        if not Confirm.ask("Are you sure you want to proceed?"):
            return
    
    try:
        # Explicitly pass force flag to purge_database
        console.print(f"[yellow]DEBUG: Calling purge_database with force={force}[/yellow]")
        purge_database(db_path=str(db_path), force=force)
        console.print(f"[green]Successfully purged all data from: {db_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error purging database: {e}[/red]")
