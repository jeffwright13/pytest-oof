"""CLI commands for analyzing test results."""
import json
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from pytest_oof.analyzer import TestDataAnalyzer

console = Console()

@click.group()
def analyze():
    """Analyze test results."""
    pass

@analyze.group()
def trends():
    """Analyze test result trends."""
    pass

@trends.command()
@click.option('--hours', default=24, help='Hours to look back')
@click.option('--min-failures', default=1, help='Minimum failures to consider')
@click.option('--sut-id', help='Filter by SUT ID')
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
def failed(hours: int, min_failures: int, sut_id: Optional[str], format: str):
    """Show recently failed tests."""
    analyzer = TestDataAnalyzer()
    failed_tests = analyzer.get_recently_failed_tests(
        hours=hours,
        min_failures=min_failures,
        sut_id=sut_id
    )
    
    if format == 'json':
        click.echo(json.dumps(failed_tests, indent=2, default=str))
    else:
        table = Table(title=f"Recently Failed Tests (Last {hours} hours)")
        table.add_column("Test ID", style="cyan")
        table.add_column("Last Failure", style="yellow")
        table.add_column("Failure Count", justify="right", style="red")
        table.add_column("Error Messages", style="red")
        
        for test_id, data in failed_tests.items():
            table.add_row(
                test_id,
                str(data['last_failure']),
                str(data['failure_count']),
                "\n".join(data['error_messages'][:3]) + 
                ("\n..." if len(data['error_messages']) > 3 else "")
            )
        
        console.print(table)

@trends.command()
@click.option('--days', default=7, help='Days to analyze')
@click.option('--min-runs', default=5, help='Minimum runs to include')
@click.option('--sut-id', help='Filter by SUT ID')
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
def durations(days: int, min_runs: int, sut_id: Optional[str], format: str):
    """Show test execution time trends."""
    analyzer = TestDataAnalyzer()
    trends = analyzer.get_duration_trends(
        days=days,
        min_runs=min_runs,
        sut_id=sut_id
    )
    
    if format == 'json':
        click.echo(json.dumps(trends, indent=2, default=str))
    else:
        table = Table(title=f"Test Duration Trends (Last {days} days)")
        table.add_column("Test ID", style="cyan")
        table.add_column("Avg Duration", justify="right", style="yellow")
        table.add_column("Min Duration", justify="right", style="green")
        table.add_column("Max Duration", justify="right", style="red")
        table.add_column("Trend", justify="right")
        table.add_column("Runs", justify="right")
        
        for test_id, data in trends.items():
            trend_str = f"{abs(data['trend']):.2f}s/day"
            if data['trend'] > 0:
                trend_str = f"[red]+{trend_str}[/red]"
            else:
                trend_str = f"[green]-{trend_str}[/green]"
                
            table.add_row(
                test_id,
                f"{data['avg_duration']:.2f}s",
                f"{data['min_duration']:.2f}s",
                f"{data['max_duration']:.2f}s",
                trend_str,
                str(data['run_count'])
            )
        
        console.print(table)

@analyze.group()
def reports():
    """Generate analysis reports."""
    pass

@reports.command()
@click.option('--days', default=30, help='Days to analyze')
@click.option('--sut-id', help='Filter by SUT ID')
@click.option('--granularity', type=click.Choice(['hour', 'day', 'week']), default='day')
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
def stability(days: int, sut_id: Optional[str], granularity: str, format: str):
    """Track test stability over time."""
    analyzer = TestDataAnalyzer()
    report = analyzer.get_stability_report(
        days=days,
        sut_id=sut_id,
        granularity=granularity
    )
    
    if format == 'json':
        click.echo(json.dumps(report, indent=2, default=str))
    else:
        # Stability Score Table
        score_table = Table(title=f"Stability Score Over Time (Last {days} days)")
        score_table.add_column("Period", style="cyan")
        score_table.add_column("Score", justify="right")
        
        for period in report['stability_score']:
            score = period['score']
            color = 'green' if score >= 0.9 else 'yellow' if score >= 0.7 else 'red'
            score_table.add_row(
                str(period['period']),
                f"[{color}]{score:.1%}[/{color}]"
            )
        
        console.print(score_table)
        console.print()
        
        # Failure Rate Table
        rate_table = Table(title="Failure Rate Over Time")
        rate_table.add_column("Period", style="cyan")
        rate_table.add_column("Rate", justify="right")
        
        for period in report['failure_rate']:
            rate = period['rate']
            color = 'green' if rate <= 0.1 else 'yellow' if rate <= 0.3 else 'red'
            rate_table.add_row(
                str(period['period']),
                f"[{color}]{rate:.1%}[/{color}]"
            )
        
        console.print(rate_table)
        console.print()
        
        # Flaky Tests Table
        flaky_table = Table(title="Flaky Tests Over Time")
        flaky_table.add_column("Period", style="cyan")
        flaky_table.add_column("Count", justify="right", style="yellow")
        flaky_table.add_column("Tests", style="red")
        
        for period in report['flaky_tests']:
            if period['count'] > 0:
                flaky_table.add_row(
                    str(period['period']),
                    str(period['count']),
                    "\n".join(period['tests'][:3]) + 
                    ("\n..." if len(period['tests']) > 3 else "")
                )
        
        console.print(flaky_table)
