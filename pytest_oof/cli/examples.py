"""CLI command to show example usage of all oof commands."""
import click
from rich.console import Console
from rich.markdown import Markdown

console = Console()

EXAMPLE_TEXT = """# pytest-oof Command Examples

## View Commands
```bash
# Terminal UI viewer
oof view tui

# Console viewer
oof view console
```

## Analyze Commands

### Test Trends
```bash
# Show recently failed tests
oof analyze trends failed --hours 24 --min-failures 1 --sut-id my-service
oof analyze trends failed --hours 48 --min-failures 3

# Show test duration trends
oof analyze trends durations --days 7 --min-runs 5 --sut-id my-service
oof analyze trends durations --days 30 --min-runs 10
```

### Reports
```bash
# Show stability report with different granularities
oof analyze reports stability --days 30 --granularity day --sut-id my-service
oof analyze reports stability --days 7 --granularity hour
oof analyze reports stability --days 90 --granularity week --sut-id my-service
```

## Export Commands

### Basic Export
```bash
# Export all results to JSON file
oof export results --output results.json
# Export all results to JSONL file
oof export results --output results.jsonl
```

### Filter by SUT
```bash
# Filter by various SUT attributes
oof export results --sut-id my-service
oof export results --sut-type microservice
oof export results --sut-version 1.2.3
oof export results --sut-env production
```

### Filter by Time
```bash
# Filter by time range
oof export results --start-time "2025-01-01 00:00:00"
oof export results --end-time "2025-02-01 00:00:00"
oof export results --start-time "2025-01-01 00:00:00" --end-time "2025-02-01 00:00:00"
```

### Filter by Test Outcome
```bash
# Filter by test result
oof export results --outcome passed
oof export results --outcome failed
oof export results --outcome skipped
oof export results --outcome xfailed
oof export results --outcome xpassed
```

### Filter by Test ID
```bash
# Filter by specific test
oof export results --test-id "test_login.py::test_successful_login"
```

### Combined Filters
```bash
# Complex query combining multiple filters
oof export results \\
    --output failed_tests.json \\
    --sut-id my-service \\
    --sut-env production \\
    --outcome failed \\
    --start-time "2025-01-01 00:00:00" \\
    --end-time "2025-02-01 00:00:00"
```

## Common Options

### Time Window Options
- `--hours` for recent trends
- `--days` for longer-term analysis
- `--start-time` and `--end-time` for exact ranges

### Filtering Options
- `--sut-id` to focus on specific system under test
- `--min-failures` and `--min-runs` for threshold filtering
- `--granularity` for time-based grouping (hour/day/week)

## Example Workflow
```bash
# 1. Check recent failures
oof analyze trends failed --hours 24

# 2. Look at stability over time
oof analyze reports stability --days 30 --granularity day --sut-id my-service

# 3. Check for slowing tests
oof analyze trends durations --days 7 --min-runs 5

# 4. Export detailed results
oof export results \\
    --output detailed_results.json \\
    --start-time "2025-01-01 00:00:00" \\
    --end-time "2025-02-01 00:00:00" \\
    --outcome failed
```

## Getting Help
```bash
# General help
oof --help

# Command group help
oof analyze --help
oof export --help

# Specific command help
oof analyze trends failed --help
oof export results --help
```
"""

@click.group()
def examples():
    """Show example commands and usage."""
    pass

@examples.command()
@click.option('--save', type=click.Path(), help='Save examples to a markdown file')
def show(save):
    """Show example commands for all oof functionality."""
    if save:
        with open(save, 'w') as f:
            f.write(EXAMPLE_TEXT)
        console.print(f"Examples saved to [green]{save}[/green]")
    else:
        md = Markdown(EXAMPLE_TEXT)
        console.print(md)
