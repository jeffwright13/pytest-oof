"""Compare test results across different environments."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from pytest_oof.analyzer import TestDataAnalyzer, SutStats

class EnvironmentComparison:
    def __init__(self, db_path: Path):
        self.analyzer = TestDataAnalyzer(db_path)
    
    def compare_environments(
        self,
        sut_id: Optional[str] = None,
        days: int = 7
    ):
        """Compare test results across environments."""
        start_time = datetime.now() - timedelta(days=days)
        
        # Get stats for each environment
        stats_by_env = {}
        all_stats = self.analyzer.get_sut_stats(
            sut_id=sut_id,
            start_time=start_time
        )
        
        # Group by environment
        for stat in all_stats:
            if stat.environment not in stats_by_env:
                stats_by_env[stat.environment] = []
            stats_by_env[stat.environment].append(stat)
        
        if not stats_by_env:
            print("No data found for comparison")
            return
        
        print(f"Environment Comparison (Last {days} days)")
        print("=" * 50)
        
        # Compare metrics across environments
        self._compare_basic_metrics(stats_by_env)
        print("\n" + "=" * 50 + "\n")
        self._compare_flaky_tests(stats_by_env)
        print("\n" + "=" * 50 + "\n")
        self._compare_sut_versions(stats_by_env)
    
    def _aggregate_stats(self, stats: List[SutStats]) -> Dict:
        """Aggregate statistics for a group of stats."""
        return {
            "total_tests": sum(s.total_tests for s in stats),
            "total_passes": sum(s.total_passes for s in stats),
            "total_failures": sum(s.total_failures for s in stats),
            "total_reruns": sum(s.total_reruns for s in stats),
            "total_sessions": sum(s.total_sessions for s in stats),
            "flaky_tests": set().union(*(set(s.flaky_tests) for s in stats)),
            "versions": set(s.sut_version for s in stats)
        }
    
    def _compare_basic_metrics(self, stats_by_env: Dict[str, List[SutStats]]):
        """Compare basic metrics across environments."""
        print("Basic Metrics")
        print("-" * 20)
        
        # Get aggregated stats for each environment
        agg_stats = {
            env: self._aggregate_stats(stats)
            for env, stats in stats_by_env.items()
        }
        
        # Calculate rates
        metrics = {
            env: {
                "pass_rate": (stats["total_passes"] / stats["total_tests"]
                            if stats["total_tests"] > 0 else 0),
                "rerun_rate": (stats["total_reruns"] / stats["total_tests"]
                             if stats["total_tests"] > 0 else 0),
                "tests_per_session": (stats["total_tests"] / stats["total_sessions"]
                                    if stats["total_sessions"] > 0 else 0)
            }
            for env, stats in agg_stats.items()
        }
        
        # Print comparison
        headers = ["Metric"] + list(stats_by_env.keys())
        print(" | ".join(f"{h:^15}" for h in headers))
        print("-" * (17 * len(headers)))
        
        for metric in ["pass_rate", "rerun_rate", "tests_per_session"]:
            values = [metric.replace("_", " ").title()] + [
                f"{metrics[env][metric]:.1%}" if metric.endswith("rate")
                else f"{metrics[env][metric]:.1f}"
                for env in stats_by_env.keys()
            ]
            print(" | ".join(f"{v:^15}" for v in values))
    
    def _compare_flaky_tests(self, stats_by_env: Dict[str, List[SutStats]]):
        """Compare flaky tests across environments."""
        print("Flaky Test Analysis")
        print("-" * 20)
        
        # Get aggregated stats for each environment
        agg_stats = {
            env: self._aggregate_stats(stats)
            for env, stats in stats_by_env.items()
        }
        
        # Find tests that are flaky in any environment
        all_flaky = set().union(*(
            stats["flaky_tests"]
            for stats in agg_stats.values()
        ))
        
        if not all_flaky:
            print("No flaky tests found in any environment")
            return
        
        print("\nFlaky Test Distribution:")
        for test in sorted(all_flaky):
            envs = [env for env, stats in agg_stats.items()
                   if test in stats["flaky_tests"]]
            print(f"\n{test}")
            print(f"Flaky in: {', '.join(envs)}")
    
    def _compare_sut_versions(self, stats_by_env: Dict[str, List[SutStats]]):
        """Compare SUT versions across environments."""
        print("Version Analysis")
        print("-" * 20)
        
        # Get aggregated stats for each environment
        agg_stats = {
            env: self._aggregate_stats(stats)
            for env, stats in stats_by_env.items()
        }
        
        # Compare versions
        all_versions = set().union(*(
            stats["versions"]
            for stats in agg_stats.values()
        ))
        
        print("\nVersion Distribution:")
        for version in sorted(all_versions):
            envs = [env for env, stats in agg_stats.items()
                   if version in stats["versions"]]
            print(f"\nVersion {version}")
            print(f"Present in: {', '.join(envs)}")

if __name__ == "__main__":
    comparison = EnvironmentComparison(Path("test_results.db"))
    # Compare all SUTs across environments
    comparison.compare_environments()
    
    # Or compare a specific SUT
    # comparison.compare_environments(sut_id="auth-service")
