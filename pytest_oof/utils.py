import time
import random
import uuid
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from strip_ansi import strip_ansi

from pytest_oof import _project_root

# OOF_FILES_DIR = Path.cwd().resolve() / "oof"
OOF_FILES_DIR = Path(_project_root) / "oof"
OOF_FILES_DIR.mkdir(exist_ok=True)
TERMINAL_OUTPUT_FILE = OOF_FILES_DIR / "oof-terminal_output.ansi"
RESULTS_FILE = OOF_FILES_DIR / "oof-results.pickle"
JSON_OUT_FILE = OOF_FILES_DIR / "oof-results.json"
HTML_FILES_DIR = OOF_FILES_DIR / "html"
HISTORY_FILE = OOF_FILES_DIR / "oof-history.pickle"


def generate_timestamp_uuid():
    # Get the current timestamp in milliseconds
    timestamp = int(time.time() * 1000)
    # Generate a random 16-bit integer (to add some randomness to avoid collisions)
    random_part = random.getrandbits(64)
    # Combine timestamp and random part
    combined = (timestamp << 64) | random_part
    # Convert the combined value to a UUID
    timestamp_uuid = uuid.UUID(int=combined)

    return str(timestamp_uuid)


@dataclass
class SessionMetadata:
    """
    'Metadata': metadata about the test run, including system under test (SUT) identification
    and test session timing information.

    Fields:
        session_id: Unique identifier for the test session
        sut_id: Unique identifier for the system under test
        sut_type: Type/category of the system (e.g., "GEMS", "production", "staging")
        sut_version: Version information about the system
        sut_environment: Environment details (e.g., "prod", "staging", "dev")
        sut_metadata: Additional SUT-specific metadata
        start_time: Start time of the test session
        stop_time: End time of the test session
        duration: Duration of the test session
    """

    session_id: str
    start_time: datetime
    stop_time: datetime
    duration: timedelta
    sut_id: str = ""
    sut_type: str = ""
    sut_version: str = ""
    sut_environment: str = ""
    sut_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sut_id": self.sut_id,
            "sut_type": self.sut_type,
            "sut_version": self.sut_version,
            "sut_environment": self.sut_environment,
            "sut_metadata": self.sut_metadata,
            "start_time": self.start_time.isoformat(),
            "stop_time": self.stop_time.isoformat(),
            "duration": self.duration.total_seconds(),
        }


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

    => Why not use Pytest's TestReport object?
    Pytest has the concept of a TestReport, which is an object that holds information about
    a single phase of a single test (setup, call, teardown). A TestReport by itself is
    not a good indication of the overall outcome of a test, which is probably what you are
    interested in as a tester. In order to determine the actual outcome of a test, you have
    to take into account all TestReport objects for that test, and run their individual
    outcomes through an algorithm internal to Pyttest. Instead of doing that, this plugin
    collects information from the console output of pytest (which I would argue is definitive).
    It then constructs a TestResult object that holds all the information you need about a
    single test:

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

    sut_id: str = ""
    sut_metadata: Dict[str, Any] = field(default_factory=dict)

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
            "sut_id": self.sut_id,
            "sut_metadata": self.sut_metadata,
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
    session_stats: TestSessionStats = None
    test_results: List[TestResult] = field(default_factory=list)

    def all_tests(self) -> List[TestResult]:
        return self.test_results

    def all_failures(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.outcome == "FAILED"]

    def all_passes(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.outcome == "PASSED"]

    def all_skips(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.outcome == "SKIPPED"]

    def all_xfails(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.outcome == "XFAIL"]

    def all_xpasses(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.outcome == "XPASS"]

    def all_errors(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.outcome == "ERROR"]

    def all_reruns(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.outcome == "RERUN"]

    def all_warnings(self) -> List[TestResult]:
        return [tr for tr in self.test_results if tr.has_warning]

    def all_warnings_unique(self) -> List[TestResult]:
        return list(set(self.all_warnings()))

    def as_list(self) -> List[Dict[str, Any]]:
        return [tr.to_dict() for tr in self.test_results]

    def to_list(self) -> List[Dict[str, Any]]:
        return self.as_list()


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
    content_stripped: str = ""


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

    test_session_starts: OutputField = field(default_factory=OutputField)
    errors: OutputField = field(default_factory=OutputField)
    failures: OutputField = field(default_factory=OutputField)
    passes: OutputField = field(default_factory=OutputField)
    warnings_summary: OutputField = field(default_factory=OutputField)
    rerun_test_summary: OutputField = field(default_factory=OutputField)
    short_test_summary: OutputField = field(default_factory=OutputField)
    lastline: OutputField = field(default_factory=OutputField)

    def to_dict(self) -> Dict[str, Any]:
        fields = [
            "test_session_starts",
            "errors",
            "failures",
            "passes",
            "warnings_summary",
            "rerun_test_summary",
            "short_test_summary",
            "lastline",
        ]

        output_dict = {}
        for field in fields:
            output_field = getattr(self, field)
            output_dict[field] = {
                "name": output_field.name,
                "content": output_field.content,
                "content_stripped": strip_ansi(output_field.content),
            }

        return output_dict


@dataclass
class Results:
    """
    'Results': a collection of all data collected during a test run, made nicely
    consumable by pytest-oof.

    'session_id': unique identifier for the test session (timestamp-based UUID)
    'session_stats': overall statistics for this test session
    'session_start_time': datetime object for the start time of the test session
    'session_stop_time': datetime object for the end time of the test session
    'session_duration': timedelta object with duration of the test session in μs
    'test_results': collection of TestResult objects for all tests in the test session
    'output_fields': collection of OutputField objects for all output fields in the
     test session's console-out
    'warnings': collection of TestResult objects for all tests that resulted in warnings
    'rerun_test_groups': collection of RerunTestGroup objects for all tests that were
     rerun during the test session
    """

    session_id: str
    session_stats: TestSessionStats
    session_start_time: datetime
    session_stop_time: datetime
    session_duration: timedelta
    test_results: List[TestResult]
    output_fields: OutputFields
    warnings: List[TestResult]
    rerun_test_groups: List[RerunTestGroup]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "session_id": self.session_id,
            "session_stats": self.session_stats.to_dict(),
            "session_start_time": self.session_start_time.isoformat(),
            "session_stop_time": self.session_stop_time.isoformat(),
            "session_duration": self.session_duration.total_seconds(),
            "test_results": [tr.to_dict() for tr in self.test_results],
            "output_fields": self.output_fields.to_dict(),
            "warnings": [w.to_dict() for w in self.warnings],
            "rerun_test_groups": [g.to_dict() for g in self.rerun_test_groups],
        }

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
            session_id=test_info["oof_session_id"],
            session_stats=test_info["oof_session_stats"],
            last_line_stripped=strip_ansi(output_fields.lastline.content),
            session_start_time=test_info["oof_session_start_time"],
            session_stop_time=test_info["oof_session_stop_time"],
            session_duration=test_info["oof_session_duration"],
            test_results=test_results,
            output_fields=output_fields,
            warnings=test_info["oof_warnings"],
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


@dataclass
class TestHistory:
    """
    TestHistory maintains a collection of Results objects from multiple test runs,
    typically associated with a single SUT over time.

    The actual SUT identification and filtering is left to client applications - this class
    simply provides the data structure and methods for storing and accessing multiple
    test runs.
    """
    results: List[Results] = field(default_factory=list)

    def add_run(self, result: Results) -> None:
        """Add a new test run result."""
        self.results.append(result)

    def get_runs(self, start_time: Optional[datetime] = None,
                end_time: Optional[datetime] = None) -> List[Results]:
        """Get test runs within the specified time range."""
        if not (start_time or end_time):
            return self.results

        filtered = self.results
        if start_time:
            filtered = [r for r in filtered
                       if r.session_start_time >= start_time]
        if end_time:
            filtered = [r for r in filtered
                       if r.session_start_time <= end_time]
        return filtered

    def get_latest_run(self) -> Optional[Results]:
        """Get the most recent test run."""
        if not self.results:
            return None
        return max(self.results,
                  key=lambda r: r.session_start_time)

    def save(self, file_path: Path) -> None:
        """Save test history to a file."""
        with open(file_path, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, file_path: Path) -> 'TestHistory':
        """Load test history from a file."""
        with open(file_path, 'rb') as f:
            return pickle.load(f)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "results": [r.to_dict() for r in self.results]
        }
