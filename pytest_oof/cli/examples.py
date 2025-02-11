"""CLI command to show example usage of all oof commands."""
import click
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

console = Console(width=120)

EXAMPLE_TEXT = """pytest-oof Command Examples

Running Tests with pytest-oof

Basic usage with required SUT ID:
    pytest --oof --oof-sut-id=my-service

With additional metadata:
    pytest --oof --oof-sut-id=my-service --oof-sut-type=api --oof-sut-version=1.0.0

Generate Example Data

Generate basic historical test data:
    oof generate data --days 30

Generate data with failure patterns:
    # Global failures (all tests fail for a time window)
    # Flaky tests (alternating pass/fail)
    # Version-specific failures
    # Environment-dependent failures
    # Performance trends over time
    oof generate data --days 14 --include-patterns

Examples of failure patterns that will be generated:
    - Global failure event: A 1-day window where all tests fail (simulates system-wide issues)
    - Flaky tests: Tests that alternate between pass/fail with varying probabilities
    - Version failures: Higher failure rates for specific SUT versions
    - Environment issues: Increased failures in certain environments (e.g., staging)
    - Performance trends: Gradual changes in failure rates over time

Generate data with custom session frequency:
    oof generate data --days 7 --min-sessions 5 --max-sessions 10

Generate fresh data by purging existing data first:
    oof generate data --days 14 --purge --include-patterns

Test Mode Commands:
    # Start test mode with default settings
    oof test-mode start

    # Start test mode with specific SUT configuration
    oof test-mode start --sut-id my-service --sut-type api --sut-version 1.0.0

    # Simulate flaky tests
    oof test-mode start --flaky-rate 0.3

    # Simulate performance degradation
    oof test-mode start --performance-trend decline

    # Generate controlled chaos with multiple failure modes
    oof test-mode start --global-failures --version-failures --environment-issues

    # Stop ongoing test mode simulation
    oof test-mode stop

    # View current test mode status
    oof test-mode status

Analyze Commands

Test Trends and Reliability:
    # Show recently failed tests
    oof analyze trends failed --hours 24 --sut-id my-service

    # Analyze test reliability
    oof analyze reports reliability --days 30 --min-runs 5 --sut-id my-service

    # Track test stability over time
    oof analyze reports stability --days 30 --sut-id my-service --granularity day

    # Show test execution time trends
    oof analyze trends durations --days 30 --min-runs 5 --sut-id my-service

    # Analyze error patterns
    oof analyze reports error-patterns --days 30 --min-occurrences 2 --sut-id my-service

Export Commands:
    # Export all results to JSON
    oof export results --output results.json

    # Export recent failures for a specific SUT
    oof export results --sut-id my-service --outcome failed --output results.jsonl

    # Export results for a specific time period
    oof export results --start-time "2025-01-01 00:00:00" --end-time "2025-02-01 00:00:00"

Help Commands:
    # Show all available commands
    oof --help

    # Show help for a specific command
    oof analyze --help
    oof export --help

Database Information:
    # Show database statistics (size, records, sessions, etc.)
    oof info

    # Get database information in JSON format
    oof info --json

    # Show these examples
    oof examples show

"""

@click.command()
@click.option("--save", type=click.Path(), help="Save examples to file")
def examples(save):
    """Show example commands and usage for pytest-oof, including test runs, data generation, failure patterns, analysis, and export."""
    # Create a Rich text object for formatted output
    text = Text()
    
    # Split the example text into lines
    lines = EXAMPLE_TEXT.split("\n")
    
    for line in lines:
        stripped = line.strip()
        
        # Section headers (bold blue)
        if stripped.endswith("Commands") or stripped == "pytest-oof Command Examples":
            text.append(line + "\n", style="bold blue")
        
        # Comments and description lines (dim gray)
        elif stripped.startswith("#"):
            text.append(line + "\n", style="dim")
        
        # Commands (green)
        elif stripped.startswith("pytest ") or stripped.startswith("python ") or stripped.startswith("oof "):
            text.append(line + "\n", style="green")
        
        # Bullet points (yellow)
        elif stripped.startswith("- "):
            text.append(line + "\n", style="yellow")
        
        # Empty lines
        elif not stripped:
            text.append("\n")
        
        # Regular text (default style)
        else:
            text.append(line + "\n")
    
    # If save option is used, write to file
    if save:
        with open(save, "w") as f:
            f.write(EXAMPLE_TEXT)
        console.print(f"Examples saved to {save}")
    else:
        # Print with a panel for better visual separation
        console.print(Panel(text, title="pytest-oof Examples", border_style="cyan"))
