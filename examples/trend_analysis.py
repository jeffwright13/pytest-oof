"""Analyze test trends over time."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pytest_oof.analyzer import TestDataAnalyzer, TestTrend

class TrendAnalyzer:
    def __init__(self, db_path: Path):
        self.analyzer = TestDataAnalyzer(db_path)
    
    def analyze_trends(
        self,
        sut_id: Optional[str] = None,
        days: int = 30,
        min_runs: int = 10
    ):
        """Analyze test trends over the specified period."""
        start_time = datetime.now() - timedelta(days=days)
        
        print(f"Test Trend Analysis (Last {days} days)")
        print("=" * 50 + "\n")
        
        self._analyze_stability_trends(sut_id, start_time, min_runs)
        print("\n" + "=" * 50 + "\n")
        self._analyze_flakiness_trends(sut_id, start_time)
        print("\n" + "=" * 50 + "\n")
        self._analyze_version_impact(sut_id, start_time, min_runs)
    
    def _analyze_stability_trends(
        self,
        sut_id: Optional[str],
        start_time: datetime,
        min_runs: int
    ):
        """Analyze test stability trends."""
        print("Test Stability Trends")
        print("-" * 20)
        
        # Get trends for the whole period
        trends = self.analyzer.analyze_test_trends(
            sut_id=sut_id,
            start_time=start_time,
            min_runs=min_runs
        )
        
        if not trends:
            print("Not enough data for trend analysis")
            return
        
        # Sort tests by stability
        stable_tests = []
        unstable_tests = []
        
        for trend in trends:
            if trend.pass_rate >= 0.95:  # 95% pass rate threshold
                stable_tests.append(trend)
            else:
                unstable_tests.append(trend)
        
        # Report findings
        total_tests = len(trends)
        print(f"\nAnalyzed {total_tests} tests with {min_runs}+ runs each")
        print(f"Stable Tests (≥95% pass rate): {len(stable_tests)} "
              f"({len(stable_tests)/total_tests:.1%})")
        print(f"Unstable Tests: {len(unstable_tests)} "
              f"({len(unstable_tests)/total_tests:.1%})")
        
        if unstable_tests:
            print("\nTop 5 Most Unstable Tests:")
            for trend in sorted(unstable_tests,
                              key=lambda t: t.pass_rate)[:5]:
                print(f"\n{trend.nodeid}")
                print(f"Pass Rate: {trend.pass_rate:.1%}")
                print(f"Runs: {trend.total_runs}")
                print(f"Avg Reruns: {trend.avg_reruns:.1f}")
    
    def _analyze_flakiness_trends(
        self,
        sut_id: Optional[str],
        start_time: datetime
    ):
        """Analyze trends in test flakiness."""
        print("Flakiness Trends")
        print("-" * 20)
        
        # Get weekly flaky test data
        weeks = 4
        weekly_data = []
        
        for week in range(weeks):
            week_end = start_time + timedelta(days=(week + 1) * 7)
            week_start = week_end - timedelta(days=7)
            
            flaky_tests = self.analyzer.get_flaky_tests(
                min_reruns=1,
                sut_id=sut_id,
                start_time=week_start,
                end_time=week_end
            )
            
            weekly_data.append((week_start, flaky_tests))
        
        # Analyze trends
        if not any(data[1] for data in weekly_data):
            print("No flaky tests found in the analysis period")
            return
        
        print("\nWeekly Flaky Test Count:")
        for week_start, flaky_tests in weekly_data:
            print(f"\nWeek of {week_start.date()}: {len(flaky_tests)} flaky tests")
            if flaky_tests:
                print("Top 3 Most Flaky:")
                for nodeid, runs, avg_reruns in sorted(
                    flaky_tests,
                    key=lambda x: x[2],
                    reverse=True
                )[:3]:
                    print(f"  - {nodeid}: {avg_reruns:.1f} avg reruns")
    
    def _analyze_version_impact(
        self,
        sut_id: Optional[str],
        start_time: datetime,
        min_runs: int
    ):
        """Analyze impact of version changes on test stability."""
        print("Version Impact Analysis")
        print("-" * 20)
        
        # Get all trends
        trends = self.analyzer.analyze_test_trends(
            sut_id=sut_id,
            start_time=start_time,
            min_runs=min_runs
        )
        
        if not trends:
            print("Not enough data for version analysis")
            return
        
        # Group tests by versions they've run on
        version_impacts: Dict[str, List[Tuple[str, float]]] = {}
        for trend in trends:
            for version in trend.sut_versions:
                if version not in version_impacts:
                    version_impacts[version] = []
                version_impacts[version].append(
                    (trend.nodeid, trend.pass_rate)
                )
        
        # Analyze each version
        print("\nTest Stability by Version:")
        for version, tests in sorted(version_impacts.items()):
            pass_rates = [rate for _, rate in tests]
            avg_pass_rate = sum(pass_rates) / len(pass_rates)
            stable_tests = sum(1 for _, rate in tests if rate >= 0.95)
            
            print(f"\nVersion: {version}")
            print(f"Tests: {len(tests)}")
            print(f"Average Pass Rate: {avg_pass_rate:.1%}")
            print(f"Stable Tests: {stable_tests} ({stable_tests/len(tests):.1%})")

if __name__ == "__main__":
    analyzer = TrendAnalyzer(Path("test_results.db"))
    # Analyze all tests
    analyzer.analyze_trends()
    
    # Or analyze a specific SUT
    # analyzer.analyze_trends(sut_id="auth-service")
