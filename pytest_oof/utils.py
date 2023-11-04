import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

OOF_FILES_DIR = Path.cwd().resolve() / "oof"
# OOF_FILES_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
OOF_FILES_DIR.mkdir(exist_ok=True)
TERMINAL_OUTPUT_FILE = OOF_FILES_DIR / "terminal_output.ansi"
RESULTS_FILE = OOF_FILES_DIR / "results.pickle"


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

    def to_dict(self) -> Dict[str, Any]:
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


@dataclass
class TestResults:
    test_results: List[TestResult] = field(default_factory=list)

    def all_tests(self) -> List[TestResult]:
        return list(self.test_results)

    def all_failures(self) -> List[TestResult]:
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "FAILED"
        ]

    def all_passes(self) -> List[TestResult]:
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "PASSED"
        ]

    def all_skips(self) -> List[TestResult]:
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "SKIPPED"
        ]

    def all_xfails(self) -> List[TestResult]:
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "XFAIL"
        ]

    def all_xpasses(self) -> List[TestResult]:
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "XPASS"
        ]

    def all_errors(self) -> List[TestResult]:
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "ERROR"
        ]

    def all_reruns(self) -> List[TestResult]:
        return [
            test_result
            for test_result in self.test_results
            if test_result.outcome == "RERUN"
        ]


@dataclass
class RerunTestGroup:
    # A 'rerun test group' consists of a single test that has been run multiple times with the
    # 'pytest-rerunfailures' plugin.
    # 'fqtn': fully-qualified test name (same for all tests in a RerunTestGroup);
    # 'final_outcome': final outcome of the test;
    # 'final_test' TestResult object for the final test (with outcome != RERUN);
    # 'forerunners':list of TestResult objects for all test that preceded final outcome.
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
    session_duration: timedelta
    test_results: List[TestResult]
    rerun_test_groups: List[RerunTestGroup]
    output_fields: OutputFields

    @classmethod
    def from_files(
        cls, results_file_path: Path, output_file_path: Optional[Path] = None
    ) -> "Results":
        terminal_output = ""
        if output_file_path:
            with open(output_file_path, "r") as f:
                terminal_output = f.read()

        with open(results_file_path, "rb") as f:
            test_info = pickle.load(f)

        # Construct the instance using the data loaded from files
        return cls(
            session_start_time=test_info["oof_session_start_time"],
            session_end_time=test_info["oof_session_end_time"],
            session_duration=test_info["oof_session_duration"],
            test_results=test_info["oof_test_results"],
            rerun_test_groups=test_info["oof_rerun_test_groups"],
            output_fields=test_info["oof_fields"],
        )
