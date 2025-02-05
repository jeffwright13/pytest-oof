"""Utility classes and functions for pytest-oof."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pytest_oof.db import db_connection

logger = logging.getLogger(__name__)

import pickle
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        python_version: Python version used for running tests
        os_info: Operating system information
        pytest_version: Pytest version used for running tests
        command_line: Command line used to run tests
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
    python_version: str = ""
    os_info: str = ""
    pytest_version: str = ""
    command_line: str = ""

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
            "python_version": self.python_version,
            "os_info": self.os_info,
            "pytest_version": self.pytest_version,
            "command_line": self.command_line,
        }


@dataclass
class TestSessionStats:
    """
    'TestSessionStats': cumulative statistics for the entire test session
    """

    num_tests: int = 0  # Total number of test runs including reruns
    num_tests_without_rerun: int = 0  # Number of unique tests (excluding reruns)
    num_tests_total: int = 0  # Total number of tests including deselected
    num_passes: int = 0
    num_failures: int = 0
    num_errors: int = 0
    num_skips: int = 0
    num_xfails: int = 0
    num_xpasses: int = 0
    num_reruns: int = 0
    num_rerun_groups: int = 0  # Number of distinct test groups that had reruns
    num_warnings: int = 0
    num_warnings_unique: int = 0
    num_deselected: int = 0  # Number of tests deselected via pytest's test selection

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class ReportBasedStats:
    """Stats collected directly from pytest test reports."""

    num_tests: int = 0  # Total number of test runs
    num_tests_total: int = 0  # Total number of tests including deselected
    num_passes: int = 0
    num_failures: int = 0
    num_errors: int = 0
    num_skips: int = 0
    num_xfails: int = 0
    num_xpasses: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


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
            "start_time": self.start_time.isoformat() if self.start_time else None,
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
            "final_test": self.final_test.to_dict() if self.final_test else None,
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
        for f in fields:
            output_field = getattr(self, f)
            output_dict[f] = {
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

    'session_metadata': metadata about the test session including timing and SUT info
    'session_stats': overall statistics for this test session
    'report_stats': statistics collected directly from pytest test reports
    'test_results': collection of TestResult objects for all tests in the test session
    'output_fields': collection of OutputField objects for all output fields in the
     test session's console-out
    'warnings': collection of TestResult objects for all tests that resulted in warnings
    'rerun_test_groups': collection of RerunTestGroup objects for all tests that were
     rerun during the test session
    """

    session_metadata: SessionMetadata
    session_stats: TestSessionStats
    report_stats: ReportBasedStats
    test_results: List[TestResult]
    output_fields: OutputFields
    warnings: List[TestResult]
    rerun_test_groups: List[RerunTestGroup]

    @classmethod
    def from_file(cls, results_file_path: Path = RESULTS_FILE) -> "Results":
        """Retrieve test run data from a results file."""
        try:
            with open(results_file_path, "rb") as f:
                test_info = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError) as e:
            raise ValueError(f"Failed to load results file {results_file_path}: {e}")

        session_metadata = SessionMetadata(
            session_id=test_info.get("oof_session_id", ""),
            start_time=test_info.get("oof_session_start_time", 0),
            stop_time=test_info.get("oof_session_stop_time", 0),
            duration=test_info.get("oof_session_duration", 0),
            sut_id=test_info.get("oof_sut_id", ""),
            sut_type=test_info.get("oof_sut_type", ""),
            sut_version=test_info.get("oof_sut_version", ""),
            sut_environment=test_info.get("oof_sut_environment", ""),
            sut_metadata=test_info.get("oof_sut_metadata", {}),
            python_version=test_info.get("oof_python_version", ""),
            os_info=test_info.get("oof_os_info", ""),
            pytest_version=test_info.get("oof_pytest_version", ""),
            command_line=test_info.get("oof_command_line", ""),
        )

        return cls(
            session_metadata=session_metadata,
            session_stats=test_info.get("oof_session_stats", TestSessionStats()),
            report_stats=test_info.get("oof_report_stats", ReportBasedStats()),
            test_results=test_info.get("oof_test_results", []),
            output_fields=test_info.get("oof_fields", OutputFields()),
            warnings=test_info.get("oof_warnings", []),
            rerun_test_groups=test_info.get("oof_rerun_test_groups", []),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Results":
        """Convert a dictionary back into a Results object."""
        # Convert session metadata
        session_metadata = SessionMetadata(
            session_id=data["session"]["session_id"],
            start_time=datetime.fromisoformat(data["session"]["start_time"]),
            stop_time=datetime.fromisoformat(
                data["session"].get("stop_time", data["session"]["start_time"])
            ),
            duration=timedelta(seconds=data["session"]["duration"]),
            sut_id=data["session"].get("sut_id", ""),
            sut_type=data["session"].get("sut_type", ""),
            sut_version=data["session"].get("sut_version", ""),
            sut_environment=data["session"].get("sut_environment", ""),
            sut_metadata=data["session"].get("sut_metadata", {}),
            python_version=data["session"].get("python_version", ""),
            os_info=data["session"].get("os_info", ""),
            pytest_version=data["session"].get("pytest_version", ""),
            command_line=data["session"].get("command_line", ""),
        )

        # Convert test results
        test_results = []
        for tr in data["test_results"]:
            test_result = TestResult(
                nodeid=tr["test_id"],
                outcome=tr["outcome"],
                start_time=datetime.fromisoformat(tr["timestamp"])
                if tr.get("timestamp")
                else None,
                duration=tr.get("duration", 0.0),
                has_warning=tr.get("has_warning", False),
                caplog=tr.get("caplog", ""),
                capstderr=tr.get("capstderr", ""),
                capstdout=tr.get("capstdout", ""),
                longreprtext=tr.get("error_message", ""),
                longreprtext_stripped=tr.get("error_message", ""),
            )
            test_results.append(test_result)

        # Convert stats
        session_stats = TestSessionStats(
            num_tests=data["session"].get("num_tests", 0),
            num_passes=data["session"].get("num_passes", 0),
            num_failures=data["session"].get("num_failures", 0),
            num_errors=data["session"].get("num_errors", 0),
            num_skips=data["session"].get("num_skips", 0),
            num_xfails=data["session"].get("num_xfails", 0),
            num_xpasses=data["session"].get("num_xpasses", 0),
            num_reruns=data["session"].get("num_reruns", 0),
            num_rerun_groups=data["session"].get("num_rerun_groups", 0),
            num_warnings=data["session"].get("num_warnings", 0),
            num_warnings_unique=data["session"].get("num_warnings_unique", 0),
            num_deselected=data["session"].get("num_deselected", 0),
        )

        # Create empty output fields for now
        output_fields = OutputFields()

        # Convert warnings and rerun groups
        warnings = []
        rerun_groups = []

        return cls(
            session_metadata=session_metadata,
            session_stats=session_stats,
            report_stats=None,  # Not stored in database
            test_results=test_results,
            output_fields=output_fields,
            warnings=warnings,
            rerun_test_groups=rerun_groups,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the Results object to a dictionary."""
        return {
            "session_metadata": self.session_metadata.to_dict(),
            "session_stats": self.session_stats.to_dict(),
            "report_stats": self.report_stats.to_dict(),
            "test_results": [tr.to_dict() for tr in self.test_results],
            "output_fields": self.output_fields.to_dict(),
            "warnings": [w.to_dict() for w in self.warnings],
            "rerun_test_groups": [rg.to_dict() for rg in self.rerun_test_groups],
        }


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
    Maintains a collection of Results objects from multiple test runs.
    """

    results: List[Results] = field(default_factory=list)
    path: Path = field(default=None)

    def __len__(self) -> int:
        """Return the number of test sessions."""
        return len(self.results)

    @property
    def test_sessions(self) -> 'TestHistory':
        """Get all test sessions."""
        return self

    def get_sut_runs(
        self,
        sut_id: str = "",
        sut_type: str = "",
        sut_version: str = "",
        sut_environment: str = "",
    ) -> List[Results]:
        """Get test runs for a specific SUT configuration.

        All specified parameters are combined with AND logic. For example:
            get_sut_runs(sut_id="my-app", sut_version="1.0.0")
        will only return results where sut_id is "my-app" AND sut_version is "1.0.0".

        Args:
            sut_id: Filter by specific SUT identifier
            sut_type: Filter by SUT type/category
            sut_version: Filter by specific SUT version
            sut_environment: Filter by specific environment

        Returns:
            List of Results objects matching ALL specified criteria.
            If no parameters are specified, returns all results.
        """
        filtered = self.results
        if sut_id:
            filtered = [r for r in filtered if r.session_metadata.sut_id == sut_id]
        if sut_type:
            filtered = [r for r in filtered if r.session_metadata.sut_type == sut_type]
        if sut_version:
            filtered = [
                r for r in filtered if r.session_metadata.sut_version == sut_version
            ]
        if sut_environment:
            filtered = [
                r
                for r in filtered
                if r.session_metadata.sut_environment == sut_environment
            ]
        return filtered

    @property
    def total_tests(self) -> int:
        """Get total number of tests across all sessions."""
        return sum(r.session_stats.num_tests for r in self.results)

    @property
    def total_passes(self) -> int:
        """Get total number of passes across all sessions."""
        return sum(r.session_stats.num_passes for r in self.results)

    @property
    def total_failures(self) -> int:
        """Get total number of failures across all sessions."""
        return sum(r.session_stats.num_failures for r in self.results)

    @property
    def total_errors(self) -> int:
        """Get total number of errors across all sessions."""
        return sum(r.session_stats.num_errors for r in self.results)

    @property
    def total_skips(self) -> int:
        """Get total number of skips across all sessions."""
        return sum(r.session_stats.num_skips for r in self.results)

    @property
    def total_xfails(self) -> int:
        """Get total number of expected failures across all sessions."""
        return sum(r.session_stats.num_xfails for r in self.results)

    @property
    def total_xpasses(self) -> int:
        """Get total number of unexpected passes across all sessions."""
        return sum(r.session_stats.num_xpasses for r in self.results)

    @property
    def total_reruns(self) -> int:
        """Get total number of reruns across all sessions."""
        return sum(r.session_stats.num_reruns for r in self.results)

    @property
    def pass_rate(self) -> float:
        """Get pass rate across all sessions."""
        total = self.total_tests
        return self.total_passes / total if total > 0 else 0.0

    @property
    def failure_rate(self) -> float:
        """Get failure rate across all sessions."""
        total = self.total_tests
        return self.total_failures / total if total > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Get error rate across all sessions."""
        total = self.total_tests
        return self.total_errors / total if total > 0 else 0.0

    @property
    def skip_rate(self) -> float:
        """Get skip rate across all sessions."""
        total = self.total_tests
        return self.total_skips / total if total > 0 else 0.0

    @property
    def xfail_rate(self) -> float:
        """Get expected failure rate across all sessions."""
        total = self.total_tests
        return self.total_xfails / total if total > 0 else 0.0

    @property
    def xpass_rate(self) -> float:
        """Get unexpected pass rate across all sessions."""
        total = self.total_tests
        return self.total_xpasses / total if total > 0 else 0.0

    def find_test_changes(self) -> Dict[str, List[str]]:
        """Find tests that have changed status."""
        return {
            "new_failures": [],
            "new_passes": [],
            "intermittent": []
        }

    def load_test_results(
        self,
        sut_id: Optional[str] = None,
        sut_type: Optional[str] = None,
        sut_version: Optional[str] = None,
        sut_env: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        last_n_sessions: Optional[int] = None,
        outcome: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> None:
        """Load test results from the database."""
        if not self.path:
            raise ValueError("Database path not set")

        with db_connection(self.path) as conn:
            c = conn.cursor()

            # Build the query
            query = """
                SELECT
                    ts.id as session_id,
                    ts.start_time,
                    ts.end_time,
                    ts.duration,
                    ts.sut_id,
                    ts.sut_type,
                    ts.sut_version,
                    ts.sut_env,
                    ts.python_version,
                    ts.os_info,
                    ts.pytest_version,
                    ts.command_line,
                    ts.report_based,
                    ts.num_tests,
                    ts.num_passes,
                    ts.num_failures,
                    ts.num_errors,
                    ts.num_skips,
                    ts.num_xfails,
                    ts.num_xpasses,
                    ts.num_reruns,
                    ts.num_rerun_groups,
                    ts.num_warnings
                FROM test_sessions ts
                WHERE 1=1
            """
            params = []

            # Add filters
            if sut_id:
                query += " AND ts.sut_id = ?"
                params.append(sut_id)
            if sut_type:
                query += " AND ts.sut_type = ?"
                params.append(sut_type)
            if sut_version:
                query += " AND ts.sut_version = ?"
                params.append(sut_version)
            if sut_env:
                query += " AND ts.sut_env = ?"
                params.append(sut_env)
            if start_time:
                query += " AND ts.start_time >= ?"
                params.append(start_time)
            if end_time:
                query += " AND ts.start_time <= ?"
                params.append(end_time)

            # Add order by and limit
            query += " ORDER BY ts.start_time DESC"
            if last_n_sessions:
                query += " LIMIT ?"
                params.append(last_n_sessions)

            # Execute query
            c.execute(query, params)
            rows = c.fetchall()

            # Clear existing results
            self.results.clear()

            # Process each session
            for row in rows:
                session_id = row[0]
                start_time = datetime.fromisoformat(row[1]) if row[1] else datetime.now()
                end_time = datetime.fromisoformat(row[2]) if row[2] else datetime.now()
                duration = timedelta(seconds=row[3] or 0)

                session_metadata = SessionMetadata(
                    session_id=str(session_id),
                    start_time=start_time,
                    stop_time=end_time,
                    duration=duration,
                    sut_id=row[4] or "",
                    sut_type=row[5] or "",
                    sut_version=row[6] or "",
                    sut_environment=row[7] or "",
                    python_version=row[8] or "",
                    os_info=row[9] or "",
                    pytest_version=row[10] or "",
                    command_line=row[11] or "",
                )

                # Create session stats from database values
                session_stats = TestSessionStats(
                    num_tests=row[13] or 0,
                    num_passes=row[14] or 0,
                    num_failures=row[15] or 0,
                    num_errors=row[16] or 0,
                    num_skips=row[17] or 0,
                    num_xfails=row[18] or 0,
                    num_xpasses=row[19] or 0,
                    num_reruns=row[20] or 0,
                    num_rerun_groups=row[21] or 0,
                    num_warnings=row[22] or 0,
                )

                # Create Results object and add to history
                result = Results(
                    session_metadata=session_metadata,
                    session_stats=session_stats,
                    report_stats=ReportBasedStats(),  # Empty report stats since we use session stats
                    test_results=[],  # We'll populate this next
                    output_fields=OutputFields(),  # Empty output fields
                    warnings=[],  # Empty warnings list
                    rerun_test_groups=[],  # Empty rerun groups
                )

                # Get test results for this session
                test_query = """
                    SELECT
                        test_id,
                        outcome,
                        timestamp,
                        duration,
                        error_message,
                        error_type,
                        error_traceback,
                        parameters,
                        has_warning,
                        caplog,
                        capstderr,
                        capstdout,
                        source_line_id
                    FROM test_results
                    WHERE session_id = ?
                """
                test_params = [session_id]

                if outcome:
                    test_query += " AND outcome = ?"
                    test_params.append(outcome)
                if test_id:
                    test_query += " AND test_id = ?"
                    test_params.append(test_id)

                c.execute(test_query, test_params)
                test_rows = c.fetchall()

                # Process test results
                for test_row in test_rows:
                    test_result = TestResult(
                        nodeid=test_row[0],
                        outcome=test_row[1],
                        start_time=datetime.fromisoformat(test_row[2]) if test_row[2] else None,
                        duration=test_row[3] or 0.0,
                        longreprtext=test_row[4] or "",
                        caplog=test_row[9] or "",
                        capstderr=test_row[10] or "",
                        capstdout=test_row[11] or "",
                        has_warning=bool(test_row[8]),
                    )
                    result.test_results.append(test_result)

                self.results.append(result)

    def add_run(self, result: Results) -> None:
        """Add a test run to the history."""
        self.results.append(result)

    def limit_runs(self, max_runs: int) -> None:
        """Limit the number of runs in history to max_runs, keeping the most recent."""
        if len(self.results) > max_runs:
            self.results = self.results[-max_runs:]

    def get_runs(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Results]:
        """Get test runs within the specified time range."""
        filtered = self.results
        if start_time:
            filtered = [
                r for r in filtered if r.session_metadata.start_time >= start_time
            ]
        if end_time:
            filtered = [
                r for r in filtered if r.session_metadata.start_time <= end_time
            ]
        return filtered

    def get_sut_runs(
        self,
        sut_id: str = "",
        sut_type: str = "",
        sut_version: str = "",
        sut_environment: str = "",
    ) -> List[Results]:
        """Get test runs for a specific SUT configuration.

        All specified parameters are combined with AND logic. For example:
            get_sut_runs(sut_id="my-app", sut_version="1.0.0")
        will only return results where sut_id is "my-app" AND sut_version is "1.0.0".

        Args:
            sut_id: Filter by specific SUT identifier
            sut_type: Filter by SUT type/category
            sut_version: Filter by specific SUT version
            sut_environment: Filter by specific environment

        Returns:
            List of Results objects matching ALL specified criteria.
            If no parameters are specified, returns all results.
        """
        filtered = self.results
        if sut_id:
            filtered = [r for r in filtered if r.session_metadata.sut_id == sut_id]
        if sut_type:
            filtered = [r for r in filtered if r.session_metadata.sut_type == sut_type]
        if sut_version:
            filtered = [
                r for r in filtered if r.session_metadata.sut_version == sut_version
            ]
        if sut_environment:
            filtered = [
                r
                for r in filtered
                if r.session_metadata.sut_environment == sut_environment
            ]
        return filtered

    def get_latest_run(self) -> Optional[Results]:
        """Get the most recent test run."""
        if not self.results:
            return None
        return max(self.results, key=lambda r: r.session_metadata.start_time)

    def save(self, file_path: Path) -> None:
        """Save test history to a file."""
        with open(file_path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, file_path: Path) -> "TestHistory":
        """Load test history from a file."""
        with open(file_path, "rb") as f:
            return pickle.load(f)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "results": [r.to_dict() for r in self.results],
        }


@dataclass
class LongitudinalAnalysis:
    """
    Provides longitudinal (over time) analysis capabilities for test histories.
    This class helps answer questions about test trends, changes, and patterns
    across multiple test sessions for a single SUT.
    """

    history: TestHistory
    sut_id: str = ""
    sut_type: str = ""
    sut_version: str = ""
    sut_environment: str = ""

    def _get_filtered_runs(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Results]:
        """Get test runs filtered by SUT and time range."""
        runs = self.history.get_sut_runs(
            sut_id=self.sut_id,
            sut_type=self.sut_type,
            sut_version=self.sut_version,
            sut_environment=self.sut_environment,
        )
        if start_time:
            runs = [r for r in runs if r.session_metadata.start_time >= start_time]
        if end_time:
            runs = [r for r in runs if r.session_metadata.start_time <= end_time]
        return runs

    def get_test_status_changes(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Track how test outcomes have changed over time.
        Returns a dict mapping test nodeids to their outcome history.
        """
        runs = self._get_filtered_runs(start_time, end_time)
        if not runs:
            return {}

        test_history = {}
        for run in sorted(runs, key=lambda r: r.session_metadata.start_time):
            for test in run.test_results:
                if test.nodeid not in test_history:
                    test_history[test.nodeid] = []
                test_history[test.nodeid].append(
                    {
                        "time": run.session_metadata.start_time,
                        "outcome": test.outcome,
                        "duration": test.duration,
                    }
                )

        return test_history

    def compare_test_sets(
        self, session_id1: str, session_id2: str
    ) -> Dict[str, List[str]]:
        """
        Compare test sets between two sessions to find:
        - Tests unique to session1
        - Tests unique to session2
        - Tests common to both sessions
        """
        runs = self._get_filtered_runs()
        run1 = next(
            (r for r in runs if r.session_metadata.session_id == session_id1), None
        )
        run2 = next(
            (r for r in runs if r.session_metadata.session_id == session_id2), None
        )

        if not run1 or not run2:
            return {"error": ["One or both session IDs not found in the specified SUT"]}

        tests1 = {t.nodeid for t in run1.test_results}
        tests2 = {t.nodeid for t in run2.test_results}

        return {
            "unique_to_session1": sorted(list(tests1 - tests2)),
            "unique_to_session2": sorted(list(tests2 - tests1)),
            "common": sorted(list(tests1 & tests2)),
        }

    def find_test_changes(self, last_n_sessions: int = 1) -> Dict[str, List[str]]:
        """
        Find tests that have changed status in recent sessions compared to their history.
        A test is considered changed if its outcome differs from its most common outcome
        in previous sessions.
        """
        changes = {"new_failures": [], "new_passes": [], "intermittent": []}

        # Get recent test runs
        runs = self._get_filtered_runs()
        if not runs:
            return changes

        # Sort runs by time and get the latest N sessions
        sorted_runs = sorted(runs, key=lambda r: r.session_metadata.start_time)
        if len(sorted_runs) <= last_n_sessions:
            return changes

        latest_runs = sorted_runs[-last_n_sessions:]
        history_runs = sorted_runs[:-last_n_sessions]  # Exclude latest N sessions

        # Build test history
        test_history = {}
        for run in history_runs:
            for test in run.test_results:
                if test.nodeid not in test_history:
                    test_history[test.nodeid] = []
                test_history[test.nodeid].append(test.outcome.lower())

        # Process latest sessions
        latest_history = {}
        for run in latest_runs[:-1]:  # All but the last session
            for test in run.test_results:
                if test.nodeid not in latest_history:
                    latest_history[test.nodeid] = []
                latest_history[test.nodeid].append(test.outcome.lower())

        # Get outcomes from the very latest session
        latest_outcomes = {}
        latest_session = latest_runs[-1]
        for test in latest_session.test_results:
            latest_outcomes[test.nodeid] = test.outcome.lower()

        # Check for changes
        for test_id, current_outcome in latest_outcomes.items():
            # Get historical outcomes
            hist_outcomes = test_history.get(test_id, [])
            recent_outcomes = latest_history.get(test_id, [])

            # Skip if no history
            if not hist_outcomes and not recent_outcomes:
                continue

            # Determine the most common outcome from history
            all_history = hist_outcomes + recent_outcomes
            if all_history:
                most_common = max(set(all_history), key=all_history.count)
            else:
                continue

            # Only show debug info if there's a status change
            if current_outcome != most_common:
                print(
                    f"Test {test_id}: current={current_outcome}, history={all_history}, most_common={most_common}"
                )

            # Check for status changes
            if most_common == "passed" and current_outcome == "failed":
                changes["new_failures"].append(test_id)
            elif most_common == "failed" and current_outcome == "passed":
                changes["new_passes"].append(test_id)

            # Check for intermittent behavior
            if len(set(all_history)) > 1:
                changes["intermittent"].append(test_id)

        # Remove duplicates and sort
        changes["new_failures"] = sorted(set(changes["new_failures"]))
        changes["new_passes"] = sorted(set(changes["new_passes"]))
        changes["intermittent"] = sorted(set(changes["intermittent"]))

        return changes

    def get_trend_stats(
        self, window_size: timedelta = timedelta(days=1)
    ) -> List[Dict[str, Any]]:
        """
        Calculate trend statistics over time using a sliding window.
        Returns statistics for each window period.
        """
        runs = self._get_filtered_runs()
        if not runs:
            return []

        sorted_runs = sorted(runs, key=lambda r: r.session_metadata.start_time)
        start_time = sorted_runs[0].session_metadata.start_time
        end_time = sorted_runs[-1].session_metadata.start_time

        # Create windows
        windows = []
        window_start = start_time
        while window_start <= end_time:
            window_end = window_start + window_size
            window_runs = [
                r
                for r in sorted_runs
                if window_start <= r.session_metadata.start_time < window_end
            ]

            if window_runs:
                # Helper function to safely sum stats that might be None
                def safe_sum(attr: str) -> int:
                    return sum(getattr(r.session_stats, attr, 0) or 0 for r in window_runs)

                stats = {
                    "window_start": window_start,
                    "window_end": window_end,
                    "num_runs": len(window_runs),
                    "num_tests": safe_sum("num_tests"),
                    "num_passes": safe_sum("num_passes"),
                    "num_failures": safe_sum("num_failures"),
                    "num_errors": safe_sum("num_errors"),
                    "num_skips": safe_sum("num_skips"),
                    "num_xfails": safe_sum("num_xfails"),
                    "num_xpasses": safe_sum("num_xpasses"),
                    "num_reruns": safe_sum("num_reruns"),
                }
                windows.append(stats)

            window_start = window_end

        return windows
