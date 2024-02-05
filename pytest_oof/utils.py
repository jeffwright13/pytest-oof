import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from strip_ansi import strip_ansi

from pytest_oof import _project_root

# OOF_FILES_DIR = Path.cwd().resolve() / "oof"
OOF_FILES_DIR = Path(_project_root) / "oof"
OOF_FILES_DIR.mkdir(exist_ok=True)
TERMINAL_OUTPUT_FILE = OOF_FILES_DIR / "oof-terminal_output.ansi"
RESULTS_FILE = OOF_FILES_DIR / "oof-results.pickle"
JSON_OUT_FILE = OOF_FILES_DIR / "oof-results.json"
HTML_FILES_DIR = OOF_FILES_DIR / "html"


@dataclass
class TestSessionStats:
    """
    'TestSessionStats': cumulative statistics for the entire test session
    """

    num_tests: int = 0
    num_passes: int = 0
    num_failures: int = 0
    num_errors: int = 0
    num_skips: int = 0
    num_xfails: int = 0
    num_xpasses: int = 0
    num_reruns: int = 0
    num_reruns_unique: int = 0
    num_warnings: int = 0
    num_warnings_unique: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "num_tests": self.num_tests,
            "num_passes": self.num_passes,
            "num_failures": self.num_failures,
            "num_errors": self.num_errors,
            "num_skips": self.num_skips,
            "num_xfails": self.num_xfails,
            "num_xpasses": self.num_xpasses,
            "num_reruns": self.num_reruns,
            "num_reruns_unique": self.num_reruns_unique,
            "num_warnings": self.num_warnings,
            "num_warnings_unique": self.num_warnings_unique,
        }


@dataclass
class TestResult:
    """
    'TestResult': a single test result, which is a single test run of a single test

    'nodeid': pytest 'node_id' (formerly fully-qualified test name, or 'fqtn')
    'outcome': outcome of the test (PASSED, FAILED, SKIPPED, etc.)
    'start_time': datetime object for the start time of the test
    'duration': duration of the test in microseconds
    'caplog': captured log output
    'capstderr': captured stderr output
    'capstdout': captured stdout output
    'longreprtext': any supplementary text output by the test
    'longreprtext_stripped': the longreprtext from above, un-ANSI-encoded
    'has_warning': whether the test resulted in a warning
    """

    nodeid: str = ""
    outcome: str = ""
    start_time: datetime = None
    duration: float = 0.0
    caplog: str = ""
    capstderr: str = ""
    capstdout: str = ""
    longreprtext: str = ""
    longreprtext_stripped: str = ""
    has_warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodeid": self.nodeid,
            "outcome": self.outcome,
            "start_time": self.start_time,
            "duration": self.duration,
            "caplog": self.caplog,
            "capstderr": self.capstderr,
            "capstdout": self.capstdout,
            "longreprtext": self.longreprtext,
            "longreprtext_stripped": self.longreprtext_stripped,
            "has_warning": self.has_warning,
        }


@dataclass
class TestResults:
    """
    A collection of TestResult objects, with convenience methods for accessing
    subsets of the collection.
    """

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

    def all_warnings(self) -> List[TestResult]:
        """search the warnings section for unique nodeids; mark all TestResult objects that have the same nodeid;
        then return list of TestResults"""

        # Populate 'has_warning' attribute for all TestResult objects
        nodeids = set([test_result.nodeid for test_result in self.test_results])
        for nodeid in nodeids:
            test_results = [
                test_result
                for test_result in self.test_results
                if test_result.nodeid == nodeid
            ]
            if len(test_results) > 1:
                for test_result in test_results:
                    test_result.has_warning = True

        return [
            test_result for test_result in self.test_results if test_result.has_warning
        ]

    def all_warnings_unique(
        self,
    ) -> List[TestResult]:
        all_warnings = self.all_warnings()

        # Uniquify the list of TestResult objects that have 'has_warning' attr
        seen_nodeids = set()
        uniques = []
        for test_result in self.test_results:
            if test_result.nodeid not in all_warnings:
                uniques.append(test_result)
                seen_nodeids.add(test_result.nodeid)

        return uniques

    def as_list(self) -> List[TestResult]:
        return list(self.test_results)

    def to_list(self) -> List[Dict[str, Any]]:
        return [test_result.to_dict() for test_result in self.test_results]


@dataclass
class RerunTestGroup:
    """
    'RerunTestGroup': a single test that has been run multiple times using
     the 'pytest-rerunfailures' plugin

    'nodeid': fully-qualified test name (same for all tests in a RerunTestGroup)
    'final_outcome': final outcome of the test
    'final_test' TestResult object for the last test run in the group (outcome != RERUN)
    'forerunners': list of TestResult objects for all test that preceded final outcome
    """

    nodeid: str = ""
    final_outcome: str = ""
    final_test: TestResult = None
    forerunners: List[TestResult] = field(default_factory=list)
    full_test_list: List[TestResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodeid": self.nodeid,
            "final_outcome": self.final_outcome,
            "final_test": self.final_test.to_dict(),
            "forerunners": [test_result.to_dict() for test_result in self.forerunners],
            "full_test_list": [
                test_result.to_dict() for test_result in self.full_test_list
            ],
        }


@dataclass
class OutputField:
    """
    An 'output field' (aka a 'section') is a block of text that is displayed in the terminal
    output during a pytest run. It provides additional information about the test run:
    warnings, errors, etc.
    """

    name: str = ""
    content: str = ""


@dataclass
class OutputFields:
    """
    A collection of all available types of OutputField objects. Not all fields will
    be present in every test run. It depends on the plugins that are installed and
    which "-r" flags are specified. This plugin forces the use of "-r RA" to ensure
    any fields that are available are included in the output.

    'test_session_starts': the second output field, which contains the start time of each test
    'errors': the third output field, which contains the error output of each test
    'failures': the fourth output field, which contains the failure output of each test
    'passes': the fifth output field, which contains the pass output of each test
    'warnings_summary': the sixth output field, which contains a summary of warnings
    'rerun_test_summary': the seventh output field, which contains a summary of rerun tests
    'short_test_summary': the eighth output field, which contains a summary of test outcomes
    'lastline': the ninth output field, which contains the last line of terminal output
    """

    test_session_starts: OutputField
    errors: OutputField
    failures: OutputField
    passes: OutputField
    warnings_summary: OutputField
    rerun_test_summary: OutputField
    short_test_summary: OutputField
    lastline: OutputField
    lastline_stripped: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_session_starts": {
                "name": self.test_session_starts.name,
                "content": self.test_session_starts.content,
            },
            "errors": {
                "name": self.errors.name,
                "content": self.errors.content,
            },
            "failures": {
                "name": self.failures.name,
                "content": self.failures.content,
            },
            "passes": {
                "name": self.passes.name,
                "content": self.passes.content,
            },
            "warnings_summary": {
                "name": self.warnings_summary.name,
                "content": self.warnings_summary.content,
            },
            "rerun_test_summary": {
                "name": self.rerun_test_summary.name,
                "content": self.rerun_test_summary.content,
            },
            "short_test_summary": {
                "name": self.short_test_summary.name,
                "content": self.short_test_summary.content,
            },
            "lastline": {
                "name": self.lastline.name,
                "content": self.lastline.content,
            },
            "last_line_stripped": strip_ansi(self.lastline.content),
        }


@dataclass
class Results:
    """
    'Results': a collection of all data collected during a test run, made nicely
    consumable by pytest-oof.

    'session_stats': overall statistics for this test session
    'session_start_time': datetime object for the start time of the test session
    'session_stop_time': datetime object for the end time of the test session
    'session_duration': timedelta object with duration of the test session in μs
    'test_results': collection of TestResult objects for all tests in the test session
    'output_fields': collection of OutputField objects for all output fields in the
     test session's console-out
    'rerun_test_groups': collection of RerunTestGroup objects for all tests that were
     rerun during the test session
    """

    session_stats: TestSessionStats
    session_start_time: datetime
    session_stop_time: datetime
    session_duration: timedelta
    test_results: List[TestResult]
    output_fields: OutputFields
    rerun_test_groups: List[RerunTestGroup]

    @classmethod
    def from_file(
        cls,
        results_file_path: Path = RESULTS_FILE,
    ) -> "Results":
        # Retrieve test run data from 'results.pickle' file
        with open(results_file_path, "rb") as f:
            test_info = pickle.load(f)
        test_results = test_info["oof_test_results"]
        output_fields = test_info["oof_fields"]

        # Construct the instance using the data loaded from file
        return cls(
            session_stats=test_info["oof_session_stats"],
            last_line_stripped=strip_ansi(output_fields.lastline.content),
            session_start_time=test_info["oof_session_start_time"],
            session_stop_time=test_info["oof_session_stop_time"],
            session_duration=test_info["oof_session_duration"],
            test_results=test_results,
            output_fields=output_fields,
            rerun_test_groups=test_info["oof_rerun_test_groups"],
        )


@dataclass
class TerminalOutput:
    """
    'TerminalOutput': the terminal output from a pytest run, with convenience methods
    """

    output: str = ""
    output_ansi: str = r""

    @classmethod
    def from_file(
        cls,
        terminal_output_file_path: Path = TERMINAL_OUTPUT_FILE,
    ) -> "TerminalOutput":
        # Retrieve terminal output data from 'terminal_output.ansi' file
        with open(terminal_output_file_path, "r") as f:
            output_ansi = f.read()
        output = strip_ansi(output_ansi)

        # Construct the instance using the data loaded from file
        return cls(
            output_ansi=output_ansi,
            output=output,
        )
