# pytest-oof Data Analysis Guide

This guide covers how to populate test data and analyze it using pytest-oof's built-in analysis functions.

## Table of Contents
- [Populating Test Data](#populating-test-data)
- [Basic Analysis Functions](#basic-analysis-functions)
- [Advanced Analysis](#advanced-analysis)
- [Database Schema](#database-schema)
- [Example Workflows](#example-workflows)

## Populating Test Data

### Running Tests with pytest-oof
```bash
# Basic usage
pytest --oof --oof-sut-id=my-system

# With full system metadata
pytest --oof \
    --oof-sut-id=auth-service \
    --oof-sut-type=microservice \
    --oof-sut-version=1.2.3 \
    --oof-sut-env=qa
```

### Database Location
By default, test results are stored in `.oof/oof-results.db`. You can specify a custom location:
```bash
pytest --oof --oof-db-path=/path/to/custom/results.db
```

## Basic Analysis Functions

### 1. Test Results Query
```python
from pytest_oof.db import get_test_results
from pathlib import Path

# Get all test results
results = get_test_results(
    db_path=Path(".oof/oof-results.db"),
    start_time=None,  # Optional start time filter
    end_time=None,    # Optional end time filter
    test_id=None,     # Optional specific test filter
    last_n_sessions=None,  # Optional limit to recent sessions
    outcome=None      # Optional outcome filter
)
```

### 2. Recent Failures Analysis
```python
from pytest_oof.db import get_recent_failures

failures = get_recent_failures(
    db_path=Path(".oof/oof-results.db"),
    hours=24,         # Look back period
    min_failures=1,   # Minimum failures to include
    sut_id=None      # Optional SUT filter
)
```

### 3. Duration Trends
```python
from pytest_oof.db import get_duration_trends

trends = get_duration_trends(
    db_path=Path(".oof/oof-results.db"),
    days=7,          # Analysis period
    min_runs=5,      # Minimum runs to include
    sut_id=None      # Optional SUT filter
)
```

## Advanced Analysis

### 1. Stability Metrics
```python
from pytest_oof.db import get_stability_metrics

metrics = get_stability_metrics(
    db_path=Path(".oof/oof-results.db"),
    days=30,
    sut_id=None,
    granularity="day"  # 'hour', 'day', or 'week'
)
```

### 2. Flaky Test Detection
```python
from pytest_oof.db import get_flaky_tests

flaky_tests = get_flaky_tests(
    db_path=Path(".oof/oof-results.db"),
    days=30,
    min_runs=5,
    flakiness_threshold=0.1,
    sut_id=None
)
```

### 3. Rerun Pattern Analysis
```python
from pytest_oof.db import get_rerun_patterns

patterns = get_rerun_patterns(
    db_path=Path(".oof/oof-results.db"),
    days=30,
    min_reruns=5,
    sut_id=None
)
```

### 4. Expected Failure Analysis
```python
from pytest_oof.db import get_xfail_trends

xfail_trends = get_xfail_trends(
    db_path=Path(".oof/oof-results.db"),
    days=30,
    granularity="day",
    sut_id=None
)
```

## Database Schema

### Main Tables

1. `sessions`
   - `session_id`: Unique identifier
   - `sut_id`: System under test identifier
   - `start_time`: Session start timestamp
   - `end_time`: Session end timestamp
   - `duration`: Total duration in seconds
   - Various test count fields (total, passed, failed, etc.)

2. `test_results`
   - `id`: Primary key
   - `session_id`: Foreign key to sessions
   - `test_id`: Test identifier
   - `outcome`: Test result (pass/fail/etc.)
   - `duration`: Test duration
   - `error_data`: JSON field for error details
   - `environment`: JSON field for test environment
   - `warnings`: JSON field for test warnings

## Example Workflows

### 1. Basic Test Analysis
```python
from pytest_oof.db import get_test_results, get_recent_failures
from pathlib import Path

db_path = Path(".oof/oof-results.db")

# Get recent test results
recent_results = get_test_results(
    db_path=db_path,
    last_n_sessions=5
)

# Check for failures
failures = get_recent_failures(
    db_path=db_path,
    hours=24
)

print(f"Found {len(failures)} failing tests in the last 24 hours")
```

### 2. Performance Analysis
```python
from pytest_oof.db import get_duration_trends
from pathlib import Path

db_path = Path(".oof/oof-results.db")

# Get duration trends for tests
trends = get_duration_trends(
    db_path=db_path,
    days=7,
    min_runs=5
)

# Print slowest tests
for test_id, stats in sorted(
    trends.items(), 
    key=lambda x: x[1]['avg_duration'],
    reverse=True
)[:5]:
    print(f"{test_id}: {stats['avg_duration']:.2f}s")
```

### 3. Stability Analysis
```python
from pytest_oof.db import get_stability_metrics, get_flaky_tests
from pathlib import Path

db_path = Path(".oof/oof-results.db")

# Get stability metrics
metrics = get_stability_metrics(
    db_path=db_path,
    days=30,
    granularity="day"
)

# Get flaky tests
flaky = get_flaky_tests(
    db_path=db_path,
    days=30,
    min_runs=5,
    flakiness_threshold=0.1
)

print("Flaky Tests:")
for test in flaky:
    print(f"{test['test_id']}: {test['flakiness_score']:.2%} flaky")
```

### 4. Comparative Analysis
```python
from pytest_oof.db import get_test_results
from pathlib import Path
from datetime import datetime, timedelta

db_path = Path(".oof/oof-results.db")
now = datetime.now()

# Compare results across different SUTs
suts = ["sut-a", "sut-b", "sut-c"]
for sut in suts:
    results = get_test_results(
        db_path=db_path,
        start_time=now - timedelta(days=7),
        sut_id=sut
    )
    
    total = len(results)
    failures = sum(1 for r in results if r.outcome == "failed")
    print(f"{sut}: {failures/total:.2%} failure rate")
```
