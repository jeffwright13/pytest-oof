# pytest-oof Examples

This directory contains real-world examples of using the pytest-oof API for test result analysis.

## Examples Overview

1. `basic_usage.py` - Simple examples of using the API
2. `weekly_report.py` - Generate a weekly test health report
3. `flaky_test_monitor.py` - Monitor and alert on flaky tests
4. `environment_comparison.py` - Compare test results across environments
5. `trend_analysis.py` - Analyze test trends over time

## Running the Examples

1. Install pytest-oof:
```bash
pip install pytest-oof
```

2. Run some tests with pytest-oof to generate data:
```bash
pytest --oof
```

3. Run any example:
```bash
python examples/weekly_report.py
```
