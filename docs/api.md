# pytest-oof API Documentation

## Overview

The pytest-oof API provides programmatic access to your test results database, allowing for deep analysis of test behavior, trends, and patterns. This is particularly useful for:

- Analyzing test reliability across different environments
- Tracking test performance over time
- Identifying flaky tests
- Generating custom reports
- Integrating with other tools and dashboards

## Getting Started

### Installation

The API is included with pytest-oof. If you haven't already installed it:

```bash
pip install pytest-oof
```

### Required Configuration

When running tests with pytest-oof, you must specify a System Under Test (SUT) ID using the `--oof-sut-id` option. This ensures that all test results can be properly attributed to specific systems or components:

```bash
# Basic usage
pytest --oof --oof-sut-id=my-service

# With additional SUT metadata
pytest --oof --oof-sut-id=auth-service --oof-sut-type=microservice --oof-sut-version=1.2.3
```

### Basic Usage

```python
from pytest_oof.analyzer import TestDataAnalyzer

# Initialize with your database path
analyzer = TestDataAnalyzer("path/to/your/test_results.db")

# Get a list of all SUTs (each test session requires a valid SUT ID)
suts = analyzer.get_all_suts()

# Get statistics for a specific SUT
stats = analyzer.get_sut_stats(sut_id="my-service")

# Note: All test results will have an associated SUT ID
# There is no concept of "tests without a SUT" in pytest-oof
```

## Database Schema

### Tables

#### sessions
Stores test session metadata and aggregate statistics.

Fields:
- `session_id` (TEXT): Unique identifier for the test session
- `sut_id` (TEXT): System Under Test identifier
- `start_time` (TIMESTAMP): Session start time
- `end_time` (TIMESTAMP): Session end time
- `duration` (INTEGER): Total session duration in seconds
- `total_tests` (INTEGER): Total number of tests run
- `passed_tests` (INTEGER): Number of passed tests
- `failed_tests` (INTEGER): Number of failed tests
- `skipped_tests` (INTEGER): Number of skipped tests
- `xfailed_tests` (INTEGER): Number of expected failures
- `xpassed_tests` (INTEGER): Number of unexpected passes
- `warnings` (INTEGER): Number of test warnings
- `errors` (INTEGER): Number of test errors
- `rerun` (INTEGER): Number of test reruns

#### test_results
Stores individual test results with JSON-formatted error and warning data.

Fields:
- `id` (INTEGER): Auto-incrementing primary key
- `session_id` (TEXT): Foreign key to sessions table
- `test_id` (TEXT): Test identifier (e.g., test file path and name)
- `outcome` (TEXT): Test result (e.g., passed, failed, skipped)
- `duration` (INTEGER): Test duration in seconds
- `error_data` (JSON): Structured error information including:
  - `message`: Error message
  - `type`: Error type
  - `traceback`: Full error traceback
- `warnings` (JSON): List of test warnings
- `rerun_count` (INTEGER): Number of times the test was rerun
- `environment` (JSON): Test environment data
- `timestamp` (TIMESTAMP): When the test was run

### Export Formats

#### JSON/JSONL Format
The exported data follows this structure:

```json
{
  "session": {
    "id": "session-uuid",
    "timing": {
      "start": "2025-02-08T10:00:00",
      "stop": "2025-02-08T10:01:00",
      "duration": 60
    },
    "sut": {
      "id": "auth-service"
    },
    "statistics": {
      "tests": {
        "total": 100,
        "passed": 95,
        "failed": 5
      },
      "warnings": {
        "total": 2
      }
    }
  },
  "test_results": {
    "passed": [{
      "id": "test_auth::test_login",
      "timing": {
        "start": "2025-02-08T10:00:01",
        "duration": 0.5
      }
    }],
    "failed": [{
      "id": "test_auth::test_logout",
      "timing": {
        "start": "2025-02-08T10:00:02",
        "duration": 0.3
      },
      "error": {
        "message": "AssertionError",
        "type": "AssertionError",
        "traceback": "..."
      }
    }]
  }
}
```

## API Reference

### TestDataAnalyzer

The main interface for analyzing test data.

#### Constructor

```python
analyzer = TestDataAnalyzer(db_path: Path)
```

- `db_path`: Path to your pytest-oof database file

#### Methods

##### get_all_suts()
```python
def get_all_suts() -> List[Dict[str, str]]
```
Returns a list of all unique System Under Test (SUT) configurations in the database.

Returns:
- List of dictionaries containing:
  - `sut_id`: Identifier for the SUT
  - `sut_type`: Type of SUT (e.g., "service", "library")
  - `version`: SUT version
  - `environment`: Test environment

Example:
```python
suts = analyzer.get_all_suts()
for sut in suts:
    print(f"Found {sut['sut_id']} version {sut['version']}")
```

##### get_sut_stats()
```python
def get_sut_stats(
    sut_id: Optional[str] = None,
    sut_type: Optional[str] = None,
    version: Optional[str] = None,
    environment: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[SutStats]
```
Get detailed statistics for SUTs matching the given criteria.

Parameters:
- `sut_id`: Filter by SUT identifier
- `sut_type`: Filter by SUT type
- `version`: Filter by SUT version
- `environment`: Filter by test environment
- `start_time`: Include only tests after this time
- `end_time`: Include only tests before this time

Returns:
- List of `SutStats` objects containing:
  - Basic SUT information (id, type, version, environment)
  - Test counts (total, passes, failures)
  - Rerun statistics
  - Time range information
  - List of flaky tests

Example:
```python
# Get stats for a specific service in production
stats = analyzer.get_sut_stats(
    sut_id="auth-service",
    environment="production",
    start_time=datetime.now() - timedelta(days=7)
)
```

##### analyze_test_trends()
```python
def analyze_test_trends(
    nodeid: Optional[str] = None,
    sut_id: Optional[str] = None,
    min_runs: int = 5,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[TestTrend]
```
Analyze trends in test behavior over time.

Parameters:
- `nodeid`: Filter by test nodeid (supports partial matches)
- `sut_id`: Filter by SUT identifier
- `min_runs`: Minimum number of test runs required for analysis
- `start_time`: Start of analysis period
- `end_time`: End of analysis period

Returns:
- List of `TestTrend` objects containing:
  - Test identification
  - Pass/fail rates
  - Rerun statistics
  - Time range information
  - Environment and version coverage

Example:
```python
# Analyze trends for tests with at least 10 runs
trends = analyzer.analyze_test_trends(
    sut_id="auth-service",
    min_runs=10
)
```

##### get_flaky_tests()
```python
def get_flaky_tests(
    min_reruns: int = 1,
    sut_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Tuple[str, int, float]]
```
Get a list of flaky tests ordered by number of reruns.

Parameters:
- `min_reruns`: Minimum number of reruns required to consider a test flaky
- `sut_id`: Filter by SUT identifier
- `start_time`: Start of analysis period
- `end_time`: End of analysis period

Returns:
- List of tuples containing:
  - Test nodeid
  - Total number of runs
  - Average number of reruns per run

Example:
```python
# Find tests that needed at least 5 reruns
flaky_tests = analyzer.get_flaky_tests(min_reruns=5)
```

## Advanced Analysis Examples

### Recently Failed Tests
Track tests that have failed in the recent past, with detailed failure information:

```python
def get_recent_failures(hours=24, min_failures=1):
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    start_time = datetime.now() - timedelta(hours=hours)
    results = analyzer.get_test_results(
        start_time=start_time,
        outcome="failed"
    )

    # Group and analyze failures
    failure_counts = {}
    for result in results:
        test_id = result["nodeid"]
        if test_id not in failure_counts:
            failure_counts[test_id] = {
                "count": 0,
                "error_types": set(),
                "environments": set()
            }

        failure_counts[test_id]["count"] += 1
        if result.get("error_type"):
            failure_counts[test_id]["error_types"].add(result["error_type"])
        failure_counts[test_id]["environments"].add(result.get("sut_env", "unknown"))

    return failure_counts

# Usage example
failures = get_recent_failures(hours=24)
for test_id, data in failures.items():
    print(f"Test: {test_id}")
    print(f"Failures: {data['count']}")
    print(f"Error Types: {', '.join(data['error_types'])}")
    print(f"Environments: {', '.join(data['environments'])}\n")
```

### Recently Fixed Tests
Identify tests that have recovered from failures:

```python
def find_fixed_tests(hours=24):
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    start_time = datetime.now() - timedelta(hours=hours)
    results = analyzer.get_test_results(start_time=start_time)

    test_status = {}
    for result in results:
        test_id = result["nodeid"]
        if test_id not in test_status:
            test_status[test_id] = {"last_failure": None, "last_pass": None}

        if result["outcome"] == "failed":
            test_status[test_id]["last_failure"] = result["start_time"]
        elif result["outcome"] == "passed":
            test_status[test_id]["last_pass"] = result["start_time"]

    fixed_tests = {
        test_id: data
        for test_id, data in test_status.items()
        if data["last_failure"] and data["last_pass"] and data["last_pass"] > data["last_failure"]
    }
    return fixed_tests

# Usage example
fixed = find_fixed_tests(hours=24)
for test_id, data in fixed.items():
    print(f"Test: {test_id}")
    print(f"Fixed at: {data['last_pass']}")
    print(f"Downtime: {data['last_pass'] - data['last_failure']}\n")
```

### SUT Comparison Over Time
Compare test results across multiple SUTs:

```python
def compare_suts(sut_ids, days=7):
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    start_time = datetime.now() - timedelta(days=days)

    comparisons = {}
    for sut_id in sut_ids:
        stats = analyzer.get_sut_stats(
            start_time=start_time,
            sut_id=sut_id
        )
        if stats:
            comparisons[sut_id] = {
                "pass_rate": stats[0].total_passes / stats[0].total_tests,
                "failure_rate": stats[0].total_failures / stats[0].total_tests,
                "avg_reruns": stats[0].total_reruns / stats[0].total_tests
            }

    return comparisons

# Usage example
suts = ["sut1", "sut2", "sut3"]
comparison = compare_suts(suts, days=7)
for sut_id, metrics in comparison.items():
    print(f"\nSUT: {sut_id}")
    print(f"Pass Rate: {metrics['pass_rate']:.1%}")
    print(f"Failure Rate: {metrics['failure_rate']:.1%}")
    print(f"Average Reruns: {metrics['avg_reruns']:.1f}")
```

### Environment Impact Analysis
Analyze how different environments affect test stability:

```python
def analyze_environment_impact(days=30):
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    start_time = datetime.now() - timedelta(days=days)
    results = analyzer.get_test_results(start_time=start_time)

    env_stats = {}
    for result in results:
        env = result.get("sut_env", "unknown")
        if env not in env_stats:
            env_stats[env] = {
                "total": 0,
                "passes": 0,
                "failures": 0,
                "reruns": 0
            }

        env_stats[env]["total"] += 1
        if result["outcome"] == "passed":
            env_stats[env]["passes"] += 1
        elif result["outcome"] == "failed":
            env_stats[env]["failures"] += 1
        env_stats[env]["reruns"] += result.get("rerun_count", 0)

    return env_stats

# Usage example
env_impact = analyze_environment_impact(days=30)
for env, stats in env_impact.items():
    print(f"\nEnvironment: {env}")
    print(f"Total Tests: {stats['total']}")
    print(f"Pass Rate: {stats['passes']/stats['total']:.1%}")
    print(f"Average Reruns: {stats['reruns']/stats['total']:.1f}")
```

### Test Duration Trends
Track test execution time trends:

```python
def analyze_duration_trends(test_id, days=30):
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    start_time = datetime.now() - timedelta(days=days)
    results = analyzer.get_test_results(
        start_time=start_time,
        test_id=test_id
    )

    durations = [
        (result["start_time"], result["duration"])
        for result in results
        if result["outcome"] == "passed"  # Only consider successful runs
    ]
    durations.sort(key=lambda x: x[0])

    return durations

# Usage example
test_id = "tests/test_feature.py::test_important_function"
trends = analyze_duration_trends(test_id, days=30)
for timestamp, duration in trends:
    print(f"Time: {timestamp}, Duration: {duration:.2f}s")
```

### Rerun Effectiveness
Analyze which tests benefit most from reruns:

```python
def analyze_rerun_effectiveness(days=30, min_reruns=5):
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    start_time = datetime.now() - timedelta(days=days)
    results = analyzer.get_test_results(start_time=start_time)

    rerun_stats = {}
    for result in results:
        test_id = result["nodeid"]
        if test_id not in rerun_stats:
            rerun_stats[test_id] = {
                "total_runs": 0,
                "needed_rerun": 0,
                "recovered": 0
            }

        rerun_stats[test_id]["total_runs"] += 1
        if result.get("rerun_count", 0) > 0:
            rerun_stats[test_id]["needed_rerun"] += 1
            if result["outcome"] == "passed":
                rerun_stats[test_id]["recovered"] += 1

    # Filter for tests with significant rerun history
    significant_reruns = {
        test_id: stats
        for test_id, stats in rerun_stats.items()
        if stats["needed_rerun"] >= min_reruns
    }

    return significant_reruns

# Usage example
rerun_stats = analyze_rerun_effectiveness(days=30, min_reruns=5)
for test_id, stats in rerun_stats.items():
    recovery_rate = stats["recovered"] / stats["needed_rerun"]
    print(f"\nTest: {test_id}")
    print(f"Total Runs: {stats['total_runs']}")
    print(f"Times Needed Rerun: {stats['needed_rerun']}")
    print(f"Recovery Rate: {recovery_rate:.1%}")
```

## Common Use Cases

### 1. Weekly Test Health Report
```python
from datetime import datetime, timedelta
from pytest_oof.analyzer import TestDataAnalyzer

def generate_weekly_report(db_path):
    analyzer = TestDataAnalyzer(db_path)
    start_time = datetime.now() - timedelta(days=7)

    # Get stats for all SUTs
    stats = analyzer.get_sut_stats(start_time=start_time)

    print("=== Weekly Test Health Report ===")
    for stat in stats:
        print(f"\nSUT: {stat.sut_id} v{stat.sut_version}")
        print(f"Pass Rate: {stat.total_passes / stat.total_tests:.1%}")
        print(f"Total Reruns: {stat.total_reruns}")
        if stat.flaky_tests:
            print("Flaky Tests:")
            for test in stat.flaky_tests:
                print(f"  - {test}")
```

### 2. Track Test Stability Over Time
```python
def analyze_test_stability(db_path, test_name):
    analyzer = TestDataAnalyzer(db_path)

    # Look at trends over the last month
    start_time = datetime.now() - timedelta(days=30)
    trends = analyzer.analyze_test_trends(
        nodeid=test_name,
        start_time=start_time
    )

    for trend in trends:
        print(f"Test: {trend.nodeid}")
        print(f"Pass Rate: {trend.pass_rate:.1%}")
        print(f"Run across versions: {', '.join(trend.sut_versions)}")
        print(f"Average reruns needed: {trend.avg_reruns:.1f}")
```

### 3. Compare Environments
```python
def compare_environments(db_path, sut_id):
    analyzer = TestDataAnalyzer(db_path)

    # Get stats for each environment
    prod_stats = analyzer.get_sut_stats(
        sut_id=sut_id,
        environment="production"
    )
    staging_stats = analyzer.get_sut_stats(
        sut_id=sut_id,
        environment="staging"
    )

    print("=== Environment Comparison ===")
    print("Production vs Staging")
    print(f"Total Tests: {prod_stats[0].total_tests} vs {staging_stats[0].total_tests}")
    print(f"Pass Rate: {prod_stats[0].total_passes/prod_stats[0].total_tests:.1%} vs {staging_stats[0].total_passes/staging_stats[0].total_tests:.1%}")
```

## Best Practices

1. **Query Optimization**
   - Use time ranges to limit data when possible
   - Filter by SUT/environment when you don't need all data
   - Use `min_runs` to focus on statistically significant results

2. **Data Analysis**
   - Consider seasonality in your analysis (time of day, day of week)
   - Look for patterns across environments and versions
   - Track both absolute numbers and rates/percentages

3. **Integration**
   - Cache results for frequently accessed queries
   - Consider running analyses in background jobs
   - Export results to monitoring systems

## Troubleshooting

Common issues and solutions:

1. **Performance Issues**
   - Use time ranges to limit data
   - Add indexes for frequently queried fields
   - Consider archiving old test results

2. **Missing Data**
   - Verify database path is correct
   - Check that pytest-oof is properly configured
   - Verify test session IDs are being generated

3. **Inconsistent Results**
   - Ensure database is not corrupted
   - Verify all test runners are using same pytest-oof version
   - Check for timezone issues in datetime comparisons
