"""CLI command to show example usage of all oof commands."""
import click
from rich.console import Console
from rich.text import Text

console = Console()

EXAMPLE_TEXT = """# pytest-oof Command Examples

## View Commands
# Terminal UI viewer
oof view tui

# Console viewer
oof view console

## Analyze Commands

### Test Trends
# Show recently failed tests
oof analyze trends failed --hours 24 --min-failures 1 --sut-id my-service
oof analyze trends failed --hours 48 --min-failures 3

# Show test duration trends
oof analyze trends durations --days 7 --min-runs 5 --sut-id my-service
oof analyze trends durations --days 30 --min-runs 10

### Reports
# Show stability report with different granularities
oof analyze reports stability --days 30 --granularity day --sut-id my-service
oof analyze reports stability --days 7 --granularity hour
oof analyze reports stability --days 90 --granularity week --sut-id my-service

## Export Commands

### Basic Export
# Export all results to JSON file
oof export results --output results.json
# Export all results to JSONL file
oof export results --output results.jsonl

### Filter by SUT
# Export results for specific SUT
oof export results --sut-id my-service --output my-service-results.json
# Export results for specific SUT type
oof export results --sut-type qa --output qa-results.json
# Export results for specific SUT version
oof export results --sut-version v1.2.3 --output v1.2.3-results.json

### Filter by Time Range
# Export last N sessions
oof export results --last-sessions 10 --output recent.json
# Export results from last 24 hours
oof export results --hours 24 --output last-24h.json
# Export results from last 7 days
oof export results --days 7 --output last-7d.json
# Export results between dates
oof export results --start-date 2023-01-01 --end-date 2023-01-31 --output january.json

### Filter by Test Outcome
# Export only failed tests
oof export results --outcome failed --output failed-tests.json
# Export only skipped tests
oof export results --outcome skipped --output skipped-tests.json

### Filter by Test ID
# Export results for specific test
oof export results --test-id test_login --output login-tests.json
"""


@click.command(
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True}
)
@click.option("--save", type=click.Path(), help="Save examples to a markdown file")
def examples(save):
    """Show example commands and usage."""
    if save:
        with open(save, "w") as f:
            f.write(EXAMPLE_TEXT)
        console.print(f"Examples saved to [green]{save}[/green]")
    else:
        # Split into sections and print each with a header
        sections = EXAMPLE_TEXT.split("\n\n")
        for section in sections:
            if section.startswith("#"):
                # It's a header
                console.print()
                console.print(Text(section.strip("#").strip(), style="bold cyan"))
            elif section.startswith("##"):
                # It's a subheader
                console.print()
                console.print(Text(section.strip("#").strip(), style="bold blue"))
            elif section.startswith("###"):
                # It's a sub-subheader
                console.print()
                console.print(Text(section.strip("#").strip(), style="bold"))
            else:
                # It's a command block
                for line in section.split("\n"):
                    if line.startswith("#"):
                        # It's a comment
                        console.print(Text(line, style="dim"))
                    elif line.strip():
                        # It's a command
                        console.print(Text(f"  {line}", style="green"))
