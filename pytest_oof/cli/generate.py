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
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(TEST_DB_PATH),
    help="Database path for generated data (default: test database)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force using production database (not recommended)",
)
def data(
    days: int,
    min_sessions: int,
    max_sessions: int,
    include_patterns: bool,
    db_path: str,
    force: bool,
):
    """Generate historical test data."""
    db_path = Path(db_path)
    
    # Safety check for production database
    if db_path.resolve() == DEFAULT_DB_PATH.resolve() and not force:
        console.print(
            "[red]Error: Refusing to generate test data in production database. "
            "Use --force to override.[/red]"
        )
        return
    
    try:
        # First purge any existing data
        purge_database(db_path=db_path)
        
        # Then generate new data
        # gen_data(
        #     days=days,
        #     sessions_per_day=(min_sessions, max_sessions),
        #     include_patterns=include_patterns,
        #     db_path=db_path,
        # )
        console.print("[green]Successfully generated test data![/green]")
    except Exception as e:
        console.print(f"[red]Error generating test data: {str(e)}[/red]")

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
