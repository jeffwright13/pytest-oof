"""Example usage of the TestDataAnalyzer API."""
from datetime import datetime, timedelta
from pathlib import Path
from pytest_oof.analyzer import TestDataAnalyzer

def main():
    # Initialize analyzer with your database
    db_path = Path("test_results.db")
    analyzer = TestDataAnalyzer(db_path)

    # 1. Get all SUTs in the database
    print("\n=== All SUTs in Database ===")
    suts = analyzer.get_all_suts()
    for sut in suts:
        print(f"- {sut['sut_id']} ({sut['version']}) in {sut['environment']}")

    # 2. Get statistics for each SUT
    print("\n=== SUT Statistics ===")
    # Look at last 30 days of data
    start_time = datetime.now() - timedelta(days=30)
    stats = analyzer.get_sut_stats(start_time=start_time)
    for stat in stats:
        print(f"\nSUT: {stat.sut_id} v{stat.sut_version}")
        print(f"Environment: {stat.environment}")
        print(f"Total Sessions: {stat.total_sessions}")
        print(f"Tests: {stat.total_tests} ({stat.total_passes} passed, {stat.total_failures} failed)")
        print(f"Total Reruns: {stat.total_reruns}")
        if stat.flaky_tests:
            print("Flaky Tests:")
            for test in stat.flaky_tests:
                print(f"  - {test}")

    # 3. Analyze test trends
    print("\n=== Test Trends ===")
    trends = analyzer.analyze_test_trends(min_runs=10)
    for trend in trends:
        print(f"\nTest: {trend.nodeid}")
        print(f"Pass Rate: {trend.pass_rate:.2%}")
        print(f"Avg Reruns: {trend.avg_reruns:.1f}")
        print(f"Total Runs: {trend.total_runs}")
        print(f"Environments: {', '.join(trend.environments)}")
        print(f"SUT Versions: {', '.join(trend.sut_versions)}")

    # 4. Find flaky tests
    print("\n=== Most Flaky Tests ===")
    flaky_tests = analyzer.get_flaky_tests(min_reruns=5)
    for nodeid, runs, avg_reruns in flaky_tests:
        print(f"- {nodeid}")
        print(f"  {runs} runs, avg {avg_reruns:.1f} reruns per run")

if __name__ == "__main__":
    main()
