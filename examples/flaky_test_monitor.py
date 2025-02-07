"""Monitor and alert on flaky tests."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from pytest_oof.analyzer import TestDataAnalyzer

class FlakyTestMonitor:
    def __init__(self, db_path: Path):
        self.analyzer = TestDataAnalyzer(db_path)
    
    def monitor(
        self,
        sut_id: Optional[str] = None,
        min_reruns: int = 2,
        days: int = 7,
        alert_threshold: float = 0.1  # 10% rerun rate threshold
    ):
        """Monitor flaky tests and generate alerts."""
        start_time = datetime.now() - timedelta(days=days)
        
        print(f"Flaky Test Monitor Report (Last {days} days)")
        print("=" * 50 + "\n")
        
        # Get flaky tests
        flaky_tests = self.analyzer.get_flaky_tests(
            min_reruns=min_reruns,
            sut_id=sut_id,
            start_time=start_time
        )
        
        if not flaky_tests:
            print("No significant test flakiness detected!")
            return
        
        # Analyze flakiness patterns
        self._analyze_patterns(flaky_tests)
        print("\n" + "=" * 50 + "\n")
        
        # Generate alerts
        self._generate_alerts(
            flaky_tests,
            alert_threshold=alert_threshold
        )
        print("\n" + "=" * 50 + "\n")
        
        # Suggest actions
        self._suggest_actions(flaky_tests)
    
    def _analyze_patterns(
        self,
        flaky_tests: List[Tuple[str, int, float]]
    ):
        """Analyze patterns in flaky tests."""
        print("Flakiness Patterns")
        print("-" * 20)
        
        # Group tests by module
        module_patterns: Dict[str, List[Tuple[str, int, float]]] = {}
        for nodeid, runs, avg_reruns in flaky_tests:
            module = nodeid.split("::")[0]
            if module not in module_patterns:
                module_patterns[module] = []
            module_patterns[module].append((nodeid, runs, avg_reruns))
        
        # Analyze module patterns
        print("\nModule Analysis:")
        for module, tests in sorted(
            module_patterns.items(),
            key=lambda x: len(x[1]),
            reverse=True
        ):
            total_runs = sum(runs for _, runs, _ in tests)
            avg_reruns = sum(
                runs * avg for _, runs, avg in tests
            ) / total_runs
            
            print(f"\n{module}")
            print(f"Flaky Tests: {len(tests)}")
            print(f"Total Runs: {total_runs}")
            print(f"Average Reruns: {avg_reruns:.1f}")
        
        # Look for common test name patterns
        print("\nCommon Test Name Patterns:")
        name_patterns: Dict[str, int] = {}
        for nodeid, _, _ in flaky_tests:
            test_name = nodeid.split("::")[-1]
            words = set(test_name.split("_"))
            for word in words:
                if len(word) > 3:  # Ignore very short words
                    name_patterns[word] = name_patterns.get(word, 0) + 1
        
        common_patterns = sorted(
            name_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        if common_patterns:
            print("\nMost common words in flaky test names:")
            for word, count in common_patterns:
                print(f"- '{word}' appears in {count} tests")
    
    def _generate_alerts(
        self,
        flaky_tests: List[Tuple[str, int, float]],
        alert_threshold: float
    ):
        """Generate alerts for concerning flaky tests."""
        print("Flaky Test Alerts")
        print("-" * 20)
        
        # High-priority alerts (high rerun rate)
        high_priority = [
            (nodeid, runs, avg)
            for nodeid, runs, avg in flaky_tests
            if (avg / runs) > alert_threshold
        ]
        
        if high_priority:
            print("\n⚠️ HIGH PRIORITY ALERTS")
            print("The following tests have excessive rerun rates:")
            for nodeid, runs, avg_reruns in sorted(
                high_priority,
                key=lambda x: x[2]/x[1],
                reverse=True
            ):
                rerun_rate = avg_reruns / runs
                print(f"\n{nodeid}")
                print(f"Rerun Rate: {rerun_rate:.1%}")
                print(f"Runs: {runs}")
                print(f"Average Reruns: {avg_reruns:.1f}")
        
        # Medium-priority alerts (consistent flakiness)
        medium_priority = [
            (nodeid, runs, avg)
            for nodeid, runs, avg in flaky_tests
            if runs >= 10 and avg >= 1
            and (nodeid, runs, avg) not in high_priority
        ]
        
        if medium_priority:
            print("\n⚠️ MEDIUM PRIORITY ALERTS")
            print("The following tests show consistent flakiness:")
            for nodeid, runs, avg_reruns in sorted(
                medium_priority,
                key=lambda x: x[2],
                reverse=True
            ):
                print(f"\n{nodeid}")
                print(f"Runs: {runs}")
                print(f"Average Reruns: {avg_reruns:.1f}")
    
    def _suggest_actions(
        self,
        flaky_tests: List[Tuple[str, int, float]]
    ):
        """Suggest actions to address flaky tests."""
        print("Recommended Actions")
        print("-" * 20)
        
        # Group tests by severity
        severe = []
        moderate = []
        mild = []
        
        for nodeid, runs, avg_reruns in flaky_tests:
            rerun_rate = avg_reruns / runs
            if rerun_rate > 0.2:  # More than 20% reruns
                severe.append((nodeid, runs, avg_reruns))
            elif avg_reruns > 2:  # More than 2 average reruns
                moderate.append((nodeid, runs, avg_reruns))
            else:
                mild.append((nodeid, runs, avg_reruns))
        
        # Suggest actions based on severity
        if severe:
            print("\nImmediate Actions Required:")
            print("The following tests need urgent attention:")
            for nodeid, runs, avg_reruns in severe:
                print(f"\n{nodeid}")
                print("Suggested actions:")
                print("1. Review test for race conditions")
                print("2. Check for external dependencies")
                print("3. Consider rewriting test")
        
        if moderate:
            print("\nMedium-term Actions:")
            print("Consider investigating these tests:")
            for nodeid, runs, avg_reruns in moderate:
                print(f"\n{nodeid}")
                print("Suggested actions:")
                print("1. Add logging to identify failure points")
                print("2. Review test stability patterns")
        
        if mild:
            print("\nMonitoring Recommended:")
            print(f"Monitor {len(mild)} tests with mild flakiness")
            print("Consider adding stability metrics to CI/CD pipeline")

if __name__ == "__main__":
    monitor = FlakyTestMonitor(Path("test_results.db"))
    # Monitor all tests
    monitor.monitor()
    
    # Or monitor a specific SUT
    # monitor.monitor(sut_id="auth-service")
