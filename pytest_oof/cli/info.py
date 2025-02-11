"""CLI command to show database statistics and information."""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_oof.cli.rich_utils import format_command_help
from pytest_oof.constants import DEFAULT_DB_PATH, TEST_DB_PATH, get_active_db

console = Console(width=120)

# Markdown help text for the info command
INFO_HELP = format_command_help(
    description="Display detailed statistics about the pytest-oof database.",
    examples="""
# Basic Usage
```bash
# Show database statistics
oof info

# Export database information as JSON
oof info --json
```

# Information Displayed
- Database type (test or production)
- Database path
- Database size
- Last modified time
- Total test sessions
- Total test results
- Unique test cases
- System Under Test (SUT) statistics
- Test outcome distribution
"""
)

def get_db_stats(db_path: Path) -> Dict[str, Any]:
    """
    Retrieve comprehensive database statistics.
    
    Args:
        db_path: Path to the SQLite database file
    
    Returns:
        Dictionary of database statistics
    """
    import sqlite3
    from datetime import datetime
    
    # Default stats dictionary
    stats = {
        'Database Type': 'Production Database' if 'oof-results.db' in str(db_path) else 'Test Database',
        'Database Path': str(db_path),
        'Database Size': f'{os.path.getsize(db_path) / (1024 * 1024):.2f} MB',
        'Last Modified': datetime.fromtimestamp(os.path.getmtime(db_path)),
        'Total Test Sessions': 0,
        'Total Test Results': 0,
        'Unique Test Cases': 0,
        'Unique SUTs': 0,
        'Unique SUT Types': 0,
        'Unique SUT Versions': 0,
        'Unique SUT Environments': 0,
        'Test Outcomes': {}
    }
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Check if required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [table[0] for table in cursor.fetchall()]
            
            if not {'test_sessions', 'test_results', 'suts'}.issubset(tables):
                return stats
            
            # Total test sessions
            cursor.execute("SELECT COUNT(*) FROM test_sessions")
            stats['Total Test Sessions'] = cursor.fetchone()[0]
            
            # Total test results
            cursor.execute("SELECT COUNT(*) FROM test_results")
            stats['Total Test Results'] = cursor.fetchone()[0]
            
            # Unique test cases
            cursor.execute("SELECT COUNT(DISTINCT test_case) FROM test_results")
            stats['Unique Test Cases'] = cursor.fetchone()[0]
            
            # Unique SUTs
            cursor.execute("SELECT COUNT(DISTINCT sut_id) FROM suts")
            stats['Unique SUTs'] = cursor.fetchone()[0]
            
            # Unique SUT Types
            cursor.execute("SELECT COUNT(DISTINCT sut_type) FROM suts")
            stats['Unique SUT Types'] = cursor.fetchone()[0]
            
            # Unique SUT Versions
            cursor.execute("SELECT COUNT(DISTINCT sut_version) FROM suts")
            stats['Unique SUT Versions'] = cursor.fetchone()[0]
            
            # Unique SUT Environments
            cursor.execute("SELECT COUNT(DISTINCT sut_environment) FROM suts")
            stats['Unique SUT Environments'] = cursor.fetchone()[0]
            
            # Test Outcomes
            cursor.execute("""
                SELECT outcome, COUNT(*) as count 
                FROM test_results 
                GROUP BY outcome 
                ORDER BY count DESC
            """)
            outcomes = cursor.fetchall()
            stats['Test Outcomes'] = {outcome: count for outcome, count in outcomes}
    
    except sqlite3.Error as e:
        console.print(f"[red]Error retrieving database statistics: {e}[/red]")
    
    return stats

def create_stats_table(stats: Dict[str, Any]) -> Table:
    """Create a Rich table with database statistics."""
    table = Table(title="Database Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    # Add rows for each statistic
    for key, value in stats.items():
        # Special handling for test outcomes
        if key == 'Test Outcomes':
            if not value:
                table.add_row(key, "No test outcomes recorded")
            else:
                outcomes_str = ", ".join(f"{k}: {v}" for k, v in value.items())
                table.add_row(key, outcomes_str)
        else:
            # Convert None to "N/A" for display
            display_value = str(value) if value is not None else "N/A"
            table.add_row(key, display_value)
    
    return table

def _prepare_json_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare stats for JSON serialization."""
    # Create a copy to avoid modifying the original
    json_stats = stats.copy()
    
    # Convert datetime to ISO format string
    if 'Last Modified' in json_stats and isinstance(json_stats['Last Modified'], datetime):
        json_stats['Last Modified'] = json_stats['Last Modified'].isoformat()
    
    return json_stats

@click.command()
@click.option('--json', is_flag=True, help='Output in JSON format')
@click.option(
    '--db-path', 
    type=click.Path(exists=True), 
    default=None, 
    help='Path to the database file (default: active database)'
)
@click.option(
    '--all',
    is_flag=True,
    help='Show info for both production and test databases',
)
def info(json, db_path, all):
    """Show database statistics and information."""
    
    # If show_all is set, display both databases
    if all:
        # Show both databases
        prod_stats = get_db_stats(DEFAULT_DB_PATH)
        
        if prod_stats:
            console.print(Panel(
                create_stats_table(prod_stats),
                title="Production Database",
                style="green"
            ))
        
        # Get test database stats
        test_stats = get_db_stats(TEST_DB_PATH)
        
        if test_stats:
            console.print(Panel(
                create_stats_table(test_stats),
                title="Test Database",
                style="blue"
            ))
        
        return
    
    # If db_path is provided, use it; otherwise, use active database
    if db_path is None:
        db_path = get_active_db()
    
    # Get stats for the specified or active database
    stats = get_db_stats(Path(db_path))
    
    # JSON output
    if json:
        import json
        print(json.dumps(_prepare_json_stats(stats), indent=2))
        return
    
    console.print(create_stats_table(stats))
