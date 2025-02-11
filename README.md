# pytest-oof: pytest Outcomes and Output-Fields

A pytest plugin providing structured, programmatic access to test results with powerful data analysis capabilities.

## Features

### Test Results Capture:
- Passes, Failures, Skips, Xfails, XPasses
- Warnings and Errors
- Rerun tracking and analysis
- Detailed error and warning data
- Test duration metrics

### Data Analysis Capabilities:
- Historical trend analysis
- Performance metrics and duration tracking
- Flaky test detection
- Stability analysis
- Cross-SUT comparisons
- Rerun pattern analysis

### SQLite Database Integration:
- Persistent storage of test results
- Efficient querying and filtering
- Time-series analysis support
- JSON-based error and warning data
- Built-in data integrity constraints

## Documentation

- [Installation and Basic Usage](docs/installation.md)
- [Data Analysis Guide](docs/data_analysis.md)
- [API Reference](docs/api.md)
- [Database Schema](docs/schema.md)

## Quick Start

### Installation

```bash
pip install pytest-oof
## Target Audience:
- Pytest plugin developers and others who need access to pytest's results after a test run has completed
- Testers who want a summary of their test run *as reported by pytest on the console* (doesn't get more authoritative than that), without having to parse pytest's complex console output
- Taylor Swift fans

# Usage

## Required Configuration

### Enabling the Plugin

```bash
pytest --oof --oof-sut-id=my-system
```

### System Under Test (SUT) ID

The `--oof-sut-id` option is **required** when running tests. This identifies which system or component is being tested, ensuring that all test results can be properly attributed and analyzed. For example:

```bash
# Running tests for the authentication service
pytest --oof --oof-sut-id=auth-service

# Running tests for a specific environment
pytest --oof --oof-sut-id=qa-ref-dist-core
```


## Demo Script DEPREACTED

First, run your pytest campaign with the required options:

```bash
# Basic usage with required SUT ID
pytest --oof --oof-sut-id=my-system

# Full example with all SUT-related options
pytest --oof --oof-sut-id=auth-service --oof-sut-type=microservice --oof-sut-version=1.2.3 --oof-sut-env=qa
```

This generates several files in the `/oof` directory:
- `oof/oof-results.db`: SQLite database containing test results in two tables:
  - `sessions`: Test session metadata and statistics
  - `test_results`: Individual test results with JSON-formatted error data
- `oof/oof-terminal_output.ansi`: Copy of the entire terminal output from your test session
- `oof/oof-results.pickle`: Pickled collection of dataclasses for easy consumption
- `oof/oof-results.json`: JSON format test results with:
  - Test session metadata (SUT info, timing, statistics)
  - Individual test results with error data and warnings
  - Available in two formats:
    - `json`: Pretty-printed JSON with indentation (default)
    - `jsonl`: JSON Lines format, one result per line

Now run the included console script `oofda`:

`$ oofda --help` (see all options)
`$ oofda --console` (generate console output showing Results and TerminalOutput objects)
`$ oofda --html` (generate an HTML file, `oofda.html`)
`$ oofda --tui` (run a TUI that displays the same information as the HTML file)


This script invokes the example code in `__main__.py`, shows how to consume the oof files, and presents basic results on the console.

Go ahead - compare the results with the last line of output from `pytest --oof` .

## As an Importable Module

Run your pytest campaign with the required options:

```bash
# Basic usage with required SUT ID
pytest --oof --oof-sut-id=my-system

# Full example with all SUT-related options
pytest --oof --oof-sut-id=auth-service --oof-sut-type=microservice --oof-sut-version=1.2.3 --oof-sut-env=qa
```

Now use as you wish:

```
from pytest_oof.utils import Results, TerminalOutput

results = Results.from_file(
    results_file_path="oof/oof-results.pickle",

terminal_output = TerminalOutput.from_file(
    terminal_output_file_path="oof/oof-terminal_output.ansi",
)
```

## As a Pytest Plugin with Custom Hook

The 'results' parameter will be filled by pytest when the hook is called.
You can then access the test session data within this block, and do whatever you want with it.

`plugin.py` or `conftest.py`:
```
@pytest.hookimpl
def pytest_oof_results(results):
    print(f"Received results: {results}")
```

### Generating Historical Test Data

You can generate historical test data using the CLI:

```bash
# Generate 7 days of test data with default settings
oof generate data

# Generate 14 days of test data with 2-5 sessions per day
oof generate data --days 14 --min-sessions 2 --max-sessions 5

# Generate data with special failure patterns
oof generate data --include-patterns

# Purge existing data before generating new data
oof generate data --purge
```

Advanced options:
- `--days`: Number of days to generate data for (default: 7)
- `--min-sessions`: Minimum number of sessions per day (default: 3)
- `--max-sessions`: Maximum number of sessions per day (default: 8)
- `--include-patterns`: Include special failure patterns like global failures and flaky tests
- `--purge`: Remove existing data before generating new data
