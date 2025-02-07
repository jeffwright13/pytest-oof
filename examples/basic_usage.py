"""Basic examples of using the pytest-oof API."""
from datetime import datetime, timedelta
from pathlib import Path
from pytest_oof.analyzer import TestDataAnalyzer

def list_all_suts():
    """List all SUTs in the database."""
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    suts = analyzer.get_all_suts()
    
    print("=== All SUTs ===")
    for sut in suts:
        print(f"SUT: {sut['sut_id']}")
        print(f"Version: {sut['version']}")
        print(f"Environment: {sut['environment']}\n")

def show_recent_stats():
    """Show statistics for the last 24 hours."""
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    start_time = datetime.now() - timedelta(hours=24)
    
    stats = analyzer.get_sut_stats(start_time=start_time)
    print("=== Last 24 Hours ===")
    for stat in stats:
        print(f"\nSUT: {stat.sut_id} v{stat.sut_version}")
        print(f"Environment: {stat.environment}")
        print(f"Total Tests: {stat.total_tests}")
        print(f"Pass Rate: {stat.total_passes / stat.total_tests:.1%}")
        print(f"Reruns: {stat.total_reruns}")

def find_flaky_tests():
    """Find tests that needed reruns."""
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    flaky_tests = analyzer.get_flaky_tests(min_reruns=1)
    
    print("=== Flaky Tests ===")
    for nodeid, runs, avg_reruns in flaky_tests:
        print(f"\nTest: {nodeid}")
        print(f"Total Runs: {runs}")
        print(f"Average Reruns: {avg_reruns:.1f}")

def analyze_specific_test(test_name):
    """Analyze a specific test's behavior."""
    analyzer = TestDataAnalyzer(Path("oof/oof-results.db"))
    trends = analyzer.analyze_test_trends(nodeid=test_name)
    
    print(f"=== Analysis for {test_name} ===")
    for trend in trends:
        print(f"Pass Rate: {trend.pass_rate:.1%}")
        print(f"Failure Rate: {trend.failure_rate:.1%}")
        print(f"Average Reruns: {trend.avg_reruns:.1f}")
        print(f"Total Runs: {trend.total_runs}")
        print(f"First Seen: {trend.first_seen}")
        print(f"Last Seen: {trend.last_seen}")
        print(f"Environments: {', '.join(trend.environments)}")
        print(f"SUT Versions: {', '.join(trend.sut_versions)}")

if __name__ == "__main__":
    list_all_suts()
    print("\n" + "="*50 + "\n")
    show_recent_stats()
    print("\n" + "="*50 + "\n")
    find_flaky_tests()
    print("\n" + "="*50 + "\n")
    analyze_specific_test("test_basic_rerun")
