"""CLI commands for analyzing test results."""
import json
import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from pytest_oof.analyzer import TestDataAnalyzer
from pytest_oof.constants import get_active_db

console = Console()

@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True}
)
@click.option(
    "--db-path",
    type=click.Path(),
    help="Override database path",
)
@click.pass_context
def analyze(ctx, db_path: Optional[str]):
    """Analyze test results."""
    ctx.ensure_object(dict)

    if db_path:
        # Store in environment so get_active_db can find it
        os.environ["OOF_CLI_DB_PATH"] = str(db_path)

    # Use get_active_db to determine which database to use
    ctx.obj["db_path"] = get_active_db()


@analyze.group()
def trends():
    """Analyze test result trends."""
    pass


@trends.command()
@click.option("--hours", default=24, help="Hours to look back")
@click.option("--min-failures", default=1, help="Minimum failures to consider")
@click.option("--sut-id", help="Filter by SUT ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def failed(ctx, hours: int, min_failures: int, sut_id: Optional[str], format: str):
    """Show recently failed tests."""
    analyzer = TestDataAnalyzer(db_path=ctx.obj["db_path"])
    failed_tests = analyzer.get_recently_failed_tests(
        hours=hours, min_failures=min_failures, sut_id=sut_id
    )

    if format == "json":
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
                str(data["last_failure"]),
                str(data["failure_count"]),
                "\n".join(data["error_messages"][:3])
                + ("\n..." if len(data["error_messages"]) > 3 else ""),
            )

        console.print(table)


@trends.command()
@click.option("--days", default=7, help="Days to analyze")
@click.option("--min-runs", default=5, help="Minimum runs to include")
@click.option("--sut-id", help="Filter by SUT ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def durations(ctx, days: int, min_runs: int, sut_id: Optional[str], format: str):
    """Show test execution time trends."""
    analyzer = TestDataAnalyzer(db_path=ctx.obj["db_path"])
    trends = analyzer.get_duration_trends(days=days, min_runs=min_runs, sut_id=sut_id)

    if format == "json":
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
            if data["trend"] > 0:
                trend_str = f"[red]+{trend_str}[/red]"
            else:
                trend_str = f"[green]-{trend_str}[/green]"

            table.add_row(
                test_id,
                f"{data['avg_duration']:.2f}s",
                f"{data['min_duration']:.2f}s",
                f"{data['max_duration']:.2f}s",
                trend_str,
                str(data["run_count"]),
            )

        console.print(table)


@analyze.group()
def reports():
    """Generate analysis reports."""
    pass


@reports.command()
@click.option("--days", default=30, help="Days to analyze")
@click.option("--min-occurrences", default=2, help="Minimum occurrences to include")
@click.option("--sut-id", help="Filter by SUT ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option("--verbose", is_flag=True, help="Show full error details")
@click.pass_context
def error_patterns(
    ctx, days: int, min_occurrences: int, sut_id: Optional[str], format: str, verbose: bool
):
    """Analyze common error patterns in test failures."""
    analyzer = TestDataAnalyzer(db_path=ctx.obj["db_path"])
    patterns = analyzer.get_error_patterns(
        days=days, min_occurrences=min_occurrences, sut_id=sut_id
    )

    if format == "json":
        click.echo(json.dumps(patterns, indent=2, default=str))
    else:
        table = Table(title=f"Common Error Patterns (Last {days} days)")
        table.add_column("Error Type", style="cyan")
        table.add_column("Occurrences", justify="right", style="yellow")
        table.add_column("Last Seen", style="magenta")
        table.add_column("Error Message", style="red")
        table.add_column("Affected Tests", style="blue")

        for pattern in patterns["error_patterns"]:
            error_msg = pattern["error_message"]
            if not verbose and len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."

            affected_tests = pattern["affected_tests"]
            if not verbose and len(affected_tests) > 3:
                affected_tests = affected_tests[:3] + ["..."]

            table.add_row(
                pattern["error_type"],
                str(pattern["occurrence_count"]),
                str(pattern["last_seen"]),
                error_msg,
                "\n".join(affected_tests),
            )

        console.print(table)


@reports.command()
@click.option("--days", default=30, help="Days to analyze")
@click.option("--min-runs", default=5, help="Minimum runs required for analysis")
@click.option("--sut-id", help="Filter by SUT ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option(
    "--reliability-threshold", default=0.95, help="Pass rate threshold for reliability"
)
@click.pass_context
def reliability(
    ctx,
    days: int,
    min_runs: int,
    sut_id: Optional[str],
    format: str,
    reliability_threshold: float,
):
    """Analyze test reliability and flakiness."""
    analyzer = TestDataAnalyzer(db_path=ctx.obj["db_path"])
    results = analyzer.get_test_reliability(
        days=days,
        min_runs=min_runs,
        sut_id=sut_id,
        reliability_threshold=reliability_threshold,
    )

    if format == "json":
        click.echo(json.dumps(results, indent=2, default=str))
        return

    # Summary table
    total_tests = len(results["tests"])
    reliable_tests = sum(1 for t in results["tests"] if t["is_reliable"])
    avg_pass_rate = (
        sum(t["pass_rate"] for t in results["tests"]) / total_tests
        if total_tests > 0
        else 0
    )

    summary = Table(title=f"Test Reliability Summary (Last {days} days)")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="yellow")

    summary.add_row("Total Tests Analyzed", str(total_tests))
    summary.add_row("Reliable Tests", str(reliable_tests))
    summary.add_row("Unreliable Tests", str(total_tests - reliable_tests))
    summary.add_row("Average Pass Rate", f"{avg_pass_rate:.1%}")

    # Details table
    details = Table(title="Test Reliability Details")
    details.add_column("Test ID", style="cyan")
    details.add_column("Pass Rate", justify="right", style="green")
    details.add_column("Runs", justify="right", style="yellow")
    details.add_column("Duration (min/avg/max)", justify="right", style="magenta")
    details.add_column("Failures", justify="right", style="red")
    details.add_column("Reruns", justify="right", style="blue")
    details.add_column("Avg Reruns", justify="right", style="blue")
    details.add_column("Errors", justify="right", style="red")
    details.add_column("Last Pass", style="green")

    for test in results["tests"]:
        details.add_row(
            test["test_id"],
            f"{test['pass_rate']:.1%}",
            str(test["total_runs"]),
            f"{test['min_duration']:.1f}/{test['avg_duration']:.1f}/{test['max_duration']:.1f}",
            str(test["failures"]),
            str(test["rerun_count"]),
            f"{test['avg_reruns_when_needed']:.1f}",
            str(test["unique_error_types"]),
            str(test["last_pass"] or "Never"),
        )

    console.print(summary)
    console.print()
    console.print(details)


@reports.command()
@click.option("--days", default=30, help="Days to analyze")
@click.option("--min-runs", default=5, help="Minimum runs required")
@click.option("--sut-id", help="Filter by SUT ID")
@click.option("--threshold", default=0.95, help="Reliability threshold")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option(
    "--show-all", is_flag=True, help="Show all tests, not just unreliable ones"
)
@click.pass_context
def reliability_old(
    ctx,
    days: int,
    min_runs: int,
    sut_id: Optional[str],
    threshold: float,
    format: str,
    show_all: bool,
):
    """Analyze test reliability and execution patterns."""
    analyzer = TestDataAnalyzer(db_path=ctx.obj["db_path"])
    report = analyzer.get_test_reliability(
        days=days, min_runs=min_runs, sut_id=sut_id, reliability_threshold=threshold
    )

    if format == "json":
        click.echo(json.dumps(report, indent=2, default=str))
    else:
        # Summary Table
        summary = Table(title=f"Test Reliability Summary (Last {days} days)")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", justify="right")

        summary.add_row("Total Tests Analyzed", str(report["summary"]["total_tests"]))
        summary.add_row(
            "Reliable Tests", f"[green]{report['summary']['reliable_tests']}[/green]"
        )
        summary.add_row(
            "Unreliable Tests", f"[red]{report['summary']['unreliable_tests']}[/red]"
        )
        summary.add_row(
            "Average Pass Rate", f"{report['summary']['avg_pass_rate']:.1%}"
        )

        console.print(summary)
        console.print()

        # Detailed Metrics Table
        metrics = Table(title="Test Reliability Details")
        metrics.add_column("Test ID", style="cyan")
        metrics.add_column("Pass Rate", justify="right")
        metrics.add_column("Runs", justify="right", style="yellow")
        metrics.add_column("Avg Duration", justify="right", style="magenta")
        metrics.add_column("Reruns", justify="right", style="red")
        metrics.add_column("Unique Errors", justify="right", style="red")

        for test in report["reliability_metrics"]:
            if show_all or not test["is_reliable"]:
                pass_rate = test["pass_rate"]
                color = (
                    "green"
                    if pass_rate >= threshold
                    else "yellow"
                    if pass_rate >= 0.8
                    else "red"
                )

                metrics.add_row(
                    test["test_id"],
                    f"[{color}]{pass_rate:.1%}[/{color}]",
                    str(test["total_runs"]),
                    f"{test['avg_duration']:.2f}s",
                    str(test["rerun_count"]),
                    str(test["unique_error_types"]),
                )

        console.print(metrics)


@reports.command()
@click.option("--days", default=30, help="Days to analyze")
@click.option("--sut-id", help="Filter by SUT ID")
@click.option(
    "--granularity", type=click.Choice(["hour", "day", "week"]), default="day"
)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option("--verbose", is_flag=True, help="Show full test details in output")
@click.pass_context
def stability(
    ctx, days: int, sut_id: Optional[str], granularity: str, format: str, verbose: bool
):
    """Track test stability over time."""
    analyzer = TestDataAnalyzer(db_path=ctx.obj["db_path"])
    report = analyzer.get_stability_report(
        days=days, sut_id=sut_id, granularity=granularity, verbose=verbose
    )

    if format == "json":
        click.echo(json.dumps(report, indent=2, default=str))
    else:
        # Stability Score Table
        score_table = Table(title=f"Stability Score Over Time (Last {days} days)")
        score_table.add_column("Period", style="cyan")
        score_table.add_column("Score", justify="right")

        for period in report["stability_score"]:
            score = period["score"]
            color = "green" if score >= 0.9 else "yellow" if score >= 0.7 else "red"
            score_table.add_row(
                str(period["period"]), f"[{color}]{score:.1%}[/{color}]"
            )

        console.print(score_table)
        console.print()

        # Failure Rate Table
        rate_table = Table(title="Failure Rate Over Time")
        rate_table.add_column("Period", style="cyan")
        rate_table.add_column("Rate", justify="right")

        for period in report["failure_rate"]:
            rate = period["rate"]
            color = "green" if rate <= 0.1 else "yellow" if rate <= 0.3 else "red"
            rate_table.add_row(str(period["period"]), f"[{color}]{rate:.1%}[/{color}]")

        console.print(rate_table)
        console.print()

        # Flaky Tests Table
        flaky_table = Table(title="Flaky Tests Over Time")
        flaky_table.add_column("Period", style="cyan")
        flaky_table.add_column("Count", justify="right", style="yellow")
        flaky_table.add_column("Tests", style="red")

        for period in report["flaky_tests"]:
            if period["count"] > 0:
                tests = period["tests"]
                if not verbose and len(tests) > 3:
                    tests = tests[:3] + ["..."]
                flaky_table.add_row(
                    str(period["period"]), str(period["count"]), "\n".join(tests)
                )

        console.print(flaky_table)
