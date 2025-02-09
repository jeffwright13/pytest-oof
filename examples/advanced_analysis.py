"""Advanced analysis examples using the pytest-oof API."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from pytest_oof.analyzer import TestDataAnalyzer


class AdvancedAnalyzer:
    """Advanced analysis helper for pytest-oof results."""

    def __init__(self, db_path: str = "./.oof/oof-results.db"):
        self.analyzer = TestDataAnalyzer(Path(db_path))

    def get_recently_failed_tests(
        self, hours: int = 24, min_failures: int = 1
    ) -> List[Dict]:
        """Get tests that have failed in the last N hours.

        Args:
            hours: Number of hours to look back
            min_failures: Minimum number of failures to include

        Returns:
            List of dicts with test info and failure details
        """
        start_time = datetime.now() - timedelta(hours=hours)
        results = self.analyzer.get_test_results(
            start_time=start_time, outcome="failed"
        )

        # Group by test ID and count failures
        failure_counts = {}
        for result in results:
            test_id = result["nodeid"]
            if test_id not in failure_counts:
                failure_counts[test_id] = {
                    "count": 0,
                    "last_failure": None,
                    "error_types": set(),
                    "environments": set(),
                }

            failure_counts[test_id]["count"] += 1
            failure_counts[test_id]["last_failure"] = max(
                result["start_time"],
                failure_counts[test_id]["last_failure"] or result["start_time"],
            )
            if result.get("error_type"):
                failure_counts[test_id]["error_types"].add(result["error_type"])
            failure_counts[test_id]["environments"].add(
                result.get("sut_env", "unknown")
            )

        # Filter and format results
        recent_failures = []
        for test_id, data in failure_counts.items():
            if data["count"] >= min_failures:
                recent_failures.append(
                    {
                        "test_id": test_id,
                        "failure_count": data["count"],
                        "last_failure": data["last_failure"],
                        "error_types": list(data["error_types"]),
                        "environments": list(data["environments"]),
                    }
                )

        return sorted(recent_failures, key=lambda x: x["last_failure"], reverse=True)

    def get_recently_fixed_tests(self, hours: int = 24) -> List[Dict]:
        """Get tests that were failing but have recently passed.

        Args:
            hours: Number of hours to look back

        Returns:
            List of dicts with test info and recovery details
        """
        start_time = datetime.now() - timedelta(hours=hours)
        results = self.analyzer.get_test_results(start_time=start_time)

        # Track tests that have both failed and passed
        test_status = {}
        for result in results:
            test_id = result["nodeid"]
            if test_id not in test_status:
                test_status[test_id] = {
                    "last_failure": None,
                    "last_pass": None,
                    "environments": set(),
                }

            if result["outcome"] == "failed":
                if (
                    test_status[test_id]["last_failure"] is None
                    or result["start_time"] > test_status[test_id]["last_failure"]
                ):
                    test_status[test_id]["last_failure"] = result["start_time"]
            elif result["outcome"] == "passed":
                if (
                    test_status[test_id]["last_pass"] is None
                    or result["start_time"] > test_status[test_id]["last_pass"]
                ):
                    test_status[test_id]["last_pass"] = result["start_time"]

            test_status[test_id]["environments"].add(result.get("sut_env", "unknown"))

        # Find tests that failed but then passed
        fixed_tests = []
        for test_id, data in test_status.items():
            if (
                data["last_failure"]
                and data["last_pass"]
                and data["last_pass"] > data["last_failure"]
            ):
                fixed_tests.append(
                    {
                        "test_id": test_id,
                        "last_failure": data["last_failure"],
                        "fixed_at": data["last_pass"],
                        "downtime": data["last_pass"] - data["last_failure"],
                        "environments": list(data["environments"]),
                    }
                )

        return sorted(fixed_tests, key=lambda x: x["fixed_at"], reverse=True)

    def compare_suts_longitudinal(
        self, sut_ids: List[str], days: int = 7, interval_hours: int = 24
    ) -> List[Dict]:
        """Compare test results across multiple SUTs over time.

        Args:
            sut_ids: List of SUT IDs to compare
            days: Number of days to analyze
            interval_hours: Size of each time interval in hours

        Returns:
            List of dicts with comparative statistics for each interval
        """
        start_time = datetime.now() - timedelta(days=days)
        intervals = []

        current_time = start_time
        while current_time < datetime.now():
            interval_end = current_time + timedelta(hours=interval_hours)
            interval_stats = {
                "start_time": current_time,
                "end_time": interval_end,
                "suts": {},
            }

            for sut_id in sut_ids:
                stats = self.analyzer.get_sut_stats(
                    start_time=current_time, end_time=interval_end, sut_id=sut_id
                )

                if stats:
                    stat = stats[0]  # Get the first (and should be only) result
                    interval_stats["suts"][sut_id] = {
                        "total_tests": stat.total_tests,
                        "pass_rate": stat.total_passes / stat.total_tests
                        if stat.total_tests > 0
                        else 0,
                        "failure_rate": stat.total_failures / stat.total_tests
                        if stat.total_tests > 0
                        else 0,
                        "error_rate": stat.total_errors / stat.total_tests
                        if stat.total_tests > 0
                        else 0,
                        "avg_reruns": stat.total_reruns / stat.total_tests
                        if stat.total_tests > 0
                        else 0,
                        "environment": stat.environment,
                    }

            intervals.append(interval_stats)
            current_time = interval_end

        return intervals


def main():
    """Run example analyses."""
    analyzer = AdvancedAnalyzer()

    # 1. Recently Failed Tests
    print("\n=== Recently Failed Tests (Last 24 Hours) ===")
    failed_tests = analyzer.get_recently_failed_tests(hours=24, min_failures=1)
    for test in failed_tests:
        print(f"\nTest: {test['test_id']}")
        print(f"Failures: {test['failure_count']}")
        print(f"Last Failure: {test['last_failure']}")
        print(f"Error Types: {', '.join(test['error_types']) or 'Unknown'}")
        print(f"Environments: {', '.join(test['environments'])}")

    # 2. Recently Fixed Tests
    print("\n=== Recently Fixed Tests (Last 24 Hours) ===")
    fixed_tests = analyzer.get_recently_fixed_tests(hours=24)
    for test in fixed_tests:
        print(f"\nTest: {test['test_id']}")
        print(f"Fixed At: {test['fixed_at']}")
        print(f"Downtime: {test['downtime']}")
        print(f"Environments: {', '.join(test['environments'])}")

    # 3. SUT Comparison
    print("\n=== SUT Comparison (Last 7 Days) ===")
    suts = ["sut1", "sut2"]  # Replace with actual SUT IDs
    comparison = analyzer.compare_suts_longitudinal(suts, days=7)

    for interval in comparison:
        print(f"\nInterval: {interval['start_time']} to {interval['end_time']}")
        for sut_id, stats in interval["suts"].items():
            print(f"\n  {sut_id}:")
            print(f"    Pass Rate: {stats['pass_rate']:.1%}")
            print(f"    Failure Rate: {stats['failure_rate']:.1%}")
            print(f"    Error Rate: {stats['error_rate']:.1%}")
            print(f"    Avg Reruns: {stats['avg_reruns']:.1f}")
            print(f"    Environment: {stats['environment']}")


if __name__ == "__main__":
    main()
