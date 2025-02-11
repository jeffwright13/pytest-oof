"""CLI command to show database statistics and information."""
import os
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console(width=120)

def get_default_db_path() -> Path:
    """Get the default database path."""
    return Path("./.oof/oof-results.db")

def get_db_stats():
    """Get statistics about the database."""
    db_path = get_default_db_path()
    if not os.path.exists(db_path):
        return None
    
    stats = {
        'db_size': os.path.getsize(db_path),
        'db_path': str(db_path),
        'last_modified': datetime.fromtimestamp(os.path.getmtime(db_path))
    }
    
    # Use raw SQL since we're just reading stats
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Get total number of sessions
        cursor.execute("""
            SELECT COUNT(DISTINCT session_id), MIN(start_time), MAX(start_time) 
            FROM sessions 
            WHERE session_id IS NOT NULL
        """)
        sessions_count, first_session, last_session = cursor.fetchone()
        stats['sessions_count'] = sessions_count
        if first_session and last_session:
            stats['first_session'] = datetime.fromisoformat(first_session)
            stats['last_session'] = datetime.fromisoformat(last_session)
            stats['date_range'] = (stats['last_session'] - stats['first_session']).days
        
        # Get total number of test results
        cursor.execute("SELECT COUNT(*) FROM test_results WHERE session_id IS NOT NULL")
        stats['results_count'] = cursor.fetchone()[0]
        
        # Get unique test cases
        cursor.execute("SELECT COUNT(DISTINCT test_id) FROM test_results WHERE test_id IS NOT NULL")
        stats['unique_tests'] = cursor.fetchone()[0]
        
        # Get SUT stats
        cursor.execute("""
            SELECT COUNT(DISTINCT sut_id) as sut_count,
                   COUNT(DISTINCT CASE WHEN sut_type != '' AND sut_type IS NOT NULL THEN sut_type END) as type_count,
                   COUNT(DISTINCT CASE WHEN sut_version != '' AND sut_version IS NOT NULL THEN sut_version END) as version_count,
                   COUNT(DISTINCT CASE WHEN sut_env != '' AND sut_env IS NOT NULL THEN sut_env END) as env_count
            FROM sessions 
            WHERE sut_id IS NOT NULL
        """)
        sut_stats = cursor.fetchone()
        stats.update({
            'sut_count': sut_stats[0],
            'sut_type_count': sut_stats[1],
            'sut_version_count': sut_stats[2],
            'sut_env_count': sut_stats[3]
        })
        
        # Get outcome distribution
        cursor.execute("""
            SELECT outcome, COUNT(*) as count
            FROM test_results
            GROUP BY outcome
            ORDER BY count DESC
        """)
        stats['outcomes'] = dict(cursor.fetchall())
    
    return stats

@click.command()
@click.option('--json', is_flag=True, help='Output in JSON format')
def info(json):
    """Show database statistics and information."""
    stats = get_db_stats()
    if not stats:
        console.print("[red]No database found.[/red] Run some tests with pytest-oof first.")
        return
    
    if json:
        import json as json_lib
        # Convert datetime objects to strings
        stats_copy = stats.copy()
        for key in ['last_modified', 'first_session', 'last_session']:
            if key in stats_copy and stats_copy[key]:
                stats_copy[key] = stats_copy[key].isoformat()
        console.print(json_lib.dumps(stats_copy, indent=2))
        return
    
    # Create a rich table for display
    table = Table(title="pytest-oof Database Information", width=100)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    # Database info
    table.add_row("Database Path", stats['db_path'])
    table.add_row("Database Size", f"{stats['db_size'] / (1024*1024):.2f} MB")
    table.add_row("Last Modified", stats['last_modified'].strftime("%Y-%m-%d %H:%M:%S"))
    
    # Test data
    table.add_row("Total Test Sessions", str(stats['sessions_count']))
    table.add_row("Total Test Results", str(stats['results_count']))
    table.add_row("Unique Test Cases", str(stats['unique_tests']))
    
    # Date range
    if stats.get('first_session'):
        table.add_row("First Session", stats['first_session'].strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Last Session", stats['last_session'].strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Date Range", f"{stats['date_range']} days")
    
    # SUT info
    table.add_row("Unique SUTs", str(stats['sut_count']))
    table.add_row("Unique SUT Types", str(stats['sut_type_count']))
    table.add_row("Unique SUT Versions", str(stats['sut_version_count']))
    table.add_row("Unique SUT Environments", str(stats['sut_env_count']))
    
    # Outcome distribution
    outcomes = []
    total = sum(stats['outcomes'].values())
    for outcome, count in stats['outcomes'].items():
        percentage = (count / total) * 100
        outcomes.append(f"{outcome}: {count} ({percentage:.1f}%)")
    table.add_row("Test Outcomes", "\n".join(outcomes))
    
    console.print(table)
