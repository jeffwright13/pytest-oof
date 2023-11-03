from dataclasses import dataclass, field
from typing import List, Optional
import pickle
from datetime import datetime
from pathlib import Path

# Define your data classes here, previously named with "Tui" prefix
@dataclass
class TestResult:
    fqtn: str = ""
    outcome: str = ""
    start_time: datetime = None
    duration: float = 0.0
    caplog: str = ""
    capstderr: str = ""
    capstdout: str = ""
    longreprtext: str = ""

    @staticmethod
    def categories():
        return [
            "fqtn",
            "outcome",
            "start_time",
            "duration",
            "caplog",
            "capstderr",
            "capstdout",
            "longreprtext",
        ]

    def to_dict(self):
        return {
            "fqtn": self.fqtn,
            "outcome": self.outcome,
            "start_time": self.start_time,
            "duration": self.duration,
            "caplog": self.caplog,
            "capstderr": self.capstderr,
            "capstdout": self.capstdout,
            "longreprtext": self.longreprtext,
        }

class TestResults:
    test_results: List[TestResult] = field(default_factory=list)

    def categories():
        return TestResult.categories()

    def all_tests(self):
        return list(self.test_results)

    def all_failures(self):
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "FAILED"
        ]

    def all_passes(self):
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "PASSED"
        ]

    def all_skipped(self):
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "SKIPPED"
        ]

    def all_xfails(self):
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "XFAIL"
        ]

    def all_xpasses(self):
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "XPASS"
        ]

    def all_errors(self):
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "ERROR"
        ]

    def all_reruns(self):
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "RERUN"
        ]
@dataclass
class RerunTestGroup:
    # A 'rerun test group' consists of a single test that has been run multiple times with the
    # 'pytest-rerunfailures' plugin.
    # 'fqtn': fully-qualified test name (same for all tests in a TuiRerunTestGroup);
    # 'final_outcome': final outcome of the test;
    # 'final_test' TuiTestResult object for the final test (with outcome != RERUN);
    # 'forerunners':list of TuiTestResult objects for all test that preceded final outcome.
    fqtn: str = ""
    final_outcome: str = ""
    final_test: TestResult = None
    forerunners: List[TestResult] = field(default_factory=list)
    full_test_list: List[TestResult] = field(default_factory=list)

@dataclass
class OutputField:
    """An 'output field' (aka a 'section') is a block of text that is displayed in the terminal
    outputduring a pytest run. It provides additional information about the test run: warnings
    errors, etc."""
    name: str = ""
    content: str = ""


@dataclass
class OutputFields:
    live_log_sessionstart: OutputField
    test_session_starts: OutputField
    errors: OutputField
    failures: OutputField
    passes: OutputField
    warnings_summary: OutputField
    rerun_test_summary: OutputField
    short_test_summary: OutputField
    lastline: OutputField


@dataclass
class Results:
    session_start_time: datetime
    session_end_time: datetime
    session_duration: float
    test_results: List[TestResult]
    rerun_test_groups: List[RerunTestGroup]
    outputfields: OutputFields

    @classmethod
    def from_files(cls, results_file_path: Path, output_file_path: Optional[Path] = None):
        with open(results_file_path, "rb") as file:
            test_info = pickle.load(file)

        terminal_output = ""
        if output_file_path:
            with open(output_file_path, "r") as file:
                terminal_output = file.read()

        # Construct the instance using the data loaded from files
        return cls(
            session_start_time=test_info["session_start_time"],
            session_end_time=test_info["session_end_time"],
            session_duration=test_info["session_duration"],
            test_results=test_info["test_results"],
            rerun_test_groups=test_info["rerun_test_groups"],
            sections=test_info["sections"],
            # ... more initialization as needed
        )

def main():
    # Usage example:
    results = Results.from_files(Path('results.pickle'), Path('terminal_out.ansi'))

    # Access the data using dot notation:
    print(results.session_start_time)
