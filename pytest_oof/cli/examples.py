"""CLI command to show example usage of all oof commands."""
import click
from rich.console import Console
from rich.text import Text

console = Console(width=120)

EXAMPLE_TEXT = """pytest-oof Command Examples

Running Tests with pytest-oof

Basic usage with required SUT ID:
    pytest --oof --oof-sut-id=my-service

With additional metadata:
    pytest --oof --oof-sut-id=my-service --oof-sut-type=api --oof-sut-version=1.0.0

Generate Example Data

Generate basic historical test data:
    python scripts/generate_historical_data.py --days 30

Generate data with failure patterns:
    # Global failures (all tests fail for a time window)
    # Flaky tests (alternating pass/fail)
    # Version-specific failures
    # Environment-dependent failures
    # Performance trends over time
    python scripts/generate_historical_data.py --days 14 --include-patterns

Examples of failure patterns that will be generated:
    - Global failure event: A 1-day window where all tests fail (simulates system-wide issues)
    - Flaky tests: Tests that alternate between pass/fail with varying probabilities
    - Version failures: Higher failure rates for specific SUT versions
    - Environment issues: Increased failures in certain environments (e.g., staging)
    - Performance trends: Gradual changes in failure rates over time

Generate data with custom session frequency:
    python scripts/generate_historical_data.py --days 7 --min-sessions 5 --max-sessions 10

Generate fresh data by purging existing data first:
    python scripts/generate_historical_data.py --days 14 --purge --include-patterns

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
    oof examples show"""

@click.command()
@click.option("--save", type=click.Path(), help="Save examples to file")
def examples(save):
    """Show example commands and usage for pytest-oof.
    
    Includes examples for:
    - Running tests with pytest-oof
    - Generating test data with various failure patterns:
        * Global failures (all tests fail for a time window)
        * Flaky tests (alternating pass/fail patterns)
        * Version-specific failures
        * Environment-dependent failures
        * Performance trends over time
    - Analyzing test results and trends
    - Exporting test data
    """
    if save:
        with open(save, "w") as f:
            f.write(EXAMPLE_TEXT)
        console.print(f"Examples saved to {save}")
    else:
        # Format the text with simple styling
        text = Text()
        for line in EXAMPLE_TEXT.split("\n"):
            if line.strip().startswith("#"):
                # Comments in dim gray
                text.append(line + "\n", style="dim")
            elif line.strip().startswith("oof") or line.strip().startswith("pytest") or line.strip().startswith("python"):
                # Commands in green
                text.append(line + "\n", style="green")
            elif not line.strip():
                # Empty lines
                text.append("\n")
            elif line.strip().endswith(":"):
                # Section headers in bold cyan
                text.append(line + "\n", style="bold cyan")
            elif line.strip().startswith("-"):
                # Pattern descriptions in yellow
                text.append(line + "\n", style="yellow")
            else:
                # Regular text
                text.append(line + "\n")
        console.print(text)
