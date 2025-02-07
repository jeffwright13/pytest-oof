"""Generate a comprehensive weekly test health report."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from pytest_oof.analyzer import TestDataAnalyzer, SutStats, TestTrend

def calculate_change(current: float, previous: float) -> tuple[float, str]:
    """Calculate percentage change and trend direction."""
    if previous == 0:
        return 0, "="
    change = ((current - previous) / previous) * 100
    direction = "↑" if change > 0 else "↓" if change < 0 else "="
    return change, direction

class WeeklyReport:
    def __init__(self, db_path: Path):
        self.analyzer = TestDataAnalyzer(db_path)
        self.now = datetime.now()
        self.this_week_start = self.now - timedelta(days=7)
        self.last_week_start = self.this_week_start - timedelta(days=7)
    
    def generate(self):
        """Generate the weekly report."""
        print("="*80)
        print(f"Test Health Report: {self.this_week_start.date()} to {self.now.date()}")
        print("="*80 + "\n")
        
        self._report_overall_health()
        print("\n" + "="*80 + "\n")
        self._report_sut_health()
        print("\n" + "="*80 + "\n")
        self._report_flaky_tests()
        print("\n" + "="*80 + "\n")
        self._report_test_trends()
    
    def _report_overall_health(self):
        """Report overall test health metrics."""
        this_week = self.analyzer.get_sut_stats(start_time=self.this_week_start)
        last_week = self.analyzer.get_sut_stats(
            start_time=self.last_week_start,
            end_time=self.this_week_start
        )
        
        # Aggregate stats
        def aggregate_stats(stats: List[SutStats]) -> Dict:
            return {
                "total_tests": sum(s.total_tests for s in stats),
                "total_passes": sum(s.total_passes for s in stats),
                "total_failures": sum(s.total_failures for s in stats),
                "total_reruns": sum(s.total_reruns for s in stats),
                "total_sessions": sum(s.total_sessions for s in stats)
            }
        
        this_week_stats = aggregate_stats(this_week)
        last_week_stats = aggregate_stats(last_week)
        
        print("Overall Health Metrics")
        print("-" * 20)
        
        # Calculate and display metrics
        metrics = [
            ("Total Test Runs", "total_tests"),
            ("Pass Rate", lambda s: s["total_passes"] / s["total_tests"] if s["total_tests"] > 0 else 0),
            ("Failure Rate", lambda s: s["total_failures"] / s["total_tests"] if s["total_tests"] > 0 else 0),
            ("Rerun Rate", lambda s: s["total_reruns"] / s["total_tests"] if s["total_tests"] > 0 else 0),
            ("Test Sessions", "total_sessions")
        ]
        
        for label, key in metrics:
            current = (this_week_stats[key] if isinstance(key, str) 
                     else key(this_week_stats))
            previous = (last_week_stats[key] if isinstance(key, str)
                      else key(last_week_stats))
            
            change, direction = calculate_change(current, previous)
            
            if isinstance(current, float):
                print(f"{label}: {current:.1%} {direction} ({change:+.1f}%)")
            else:
                print(f"{label}: {current} {direction} ({change:+.1f}%)")
    
    def _report_sut_health(self):
        """Report health metrics for each SUT."""
        print("SUT Health Metrics")
        print("-" * 20)
        
        stats = self.analyzer.get_sut_stats(start_time=self.this_week_start)
        for stat in stats:
            print(f"\nSUT: {stat.sut_id} v{stat.sut_version}")
            print(f"Environment: {stat.environment}")
            print(f"Test Sessions: {stat.total_sessions}")
            print(f"Total Tests: {stat.total_tests}")
            print(f"Pass Rate: {stat.total_passes / stat.total_tests:.1%}")
            print(f"Reruns: {stat.total_reruns}")
            if stat.flaky_tests:
                print("Top Flaky Tests:")
                for test in stat.flaky_tests[:3]:  # Show top 3
                    print(f"  - {test}")
    
    def _report_flaky_tests(self):
        """Report on flaky tests."""
        print("Flaky Test Analysis")
        print("-" * 20)
        
        flaky_tests = self.analyzer.get_flaky_tests(
            min_reruns=2,
            start_time=self.this_week_start
        )
        
        if not flaky_tests:
            print("No significantly flaky tests found this week!")
            return
        
        print("\nTop 5 Most Flaky Tests:")
        for nodeid, runs, avg_reruns in flaky_tests[:5]:
            print(f"\nTest: {nodeid}")
            print(f"Runs this week: {runs}")
            print(f"Average reruns needed: {avg_reruns:.1f}")
    
    def _report_test_trends(self):
        """Report on test trends."""
        print("Test Trends")
        print("-" * 20)
        
        trends = self.analyzer.analyze_test_trends(
            min_runs=10,
            start_time=self.this_week_start
        )
        
        if not trends:
            print("Not enough data for trend analysis")
            return
        
        # Find tests with significant changes
        significant_changes = []
        for trend in trends:
            # Look at historical data
            historical = self.analyzer.analyze_test_trends(
                nodeid=trend.nodeid,
                start_time=self.last_week_start,
                end_time=self.this_week_start
            )
            
            if not historical:
                continue
                
            hist = historical[0]
            change, _ = calculate_change(trend.pass_rate, hist.pass_rate)
            if abs(change) >= 5:  # 5% change threshold
                significant_changes.append((trend, change))
        
        if significant_changes:
            print("\nTests with Significant Changes:")
            for trend, change in sorted(significant_changes, 
                                     key=lambda x: abs(x[1]), 
                                     reverse=True)[:5]:
                print(f"\nTest: {trend.nodeid}")
                print(f"Pass Rate: {trend.pass_rate:.1%} ({change:+.1f}% change)")
                print(f"Runs: {trend.total_runs}")
                print(f"Environments: {', '.join(trend.environments)}")

if __name__ == "__main__":
    report = WeeklyReport(Path("test_results.db"))
    report.generate()
