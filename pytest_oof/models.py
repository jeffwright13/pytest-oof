"""Data models for pytest-oof."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class TestResult:
    """'TestResult': a single test result, which is a single test run of a single test.

    Fields:
    'nodeid': pytest 'node_id' (test identifier)
    'outcome': outcome of the test (PASSED, FAILED, SKIPPED, etc.)
    'start_time': datetime object for the start time of the test
    'duration': duration of the test in microseconds
    'error_message': error message if test failed
    'error_type': type of error if test failed
    'error_traceback': error traceback if test failed
    'has_warning': whether the test resulted in a warning
    'longreprtext': full representation of test failure or error
    'rerun_count': number of times this test was rerun (0 if not rerun)
    """

    sut_id: str = ""
    sut_metadata: Dict[str, Any] = field(default_factory=dict)
    nodeid: str = ""
    outcome: str = ""
    start_time: datetime = None
    duration: float = 0.0
    error_message: str = ""
    error_type: str = ""
    error_traceback: str = ""
    has_warning: bool = False
    longreprtext: str = ""
    caplog: str = ""
    capstdout: str = ""
    capstderr: str = ""
    rerun_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sut_id": self.sut_id,
            "sut_metadata": self.sut_metadata,
            "nodeid": self.nodeid,
            "outcome": self.outcome,
            "start_time": self.start_time,
            "duration": self.duration,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "error_traceback": self.error_traceback,
            "has_warning": self.has_warning,
            "longreprtext": self.longreprtext,
            "caplog": self.caplog,
            "capstdout": self.capstdout,
            "capstderr": self.capstderr,
            "rerun_count": self.rerun_count,
        }


@dataclass
class TestSessionStats:
    """'TestSessionStats': cumulative statistics for the entire test session."""

    num_tests: int = 0
    num_tests_without_rerun: int = 0
    num_tests_total: int = 0
    num_passes: int = 0
    num_failures: int = 0
    num_errors: int = 0
    num_skips: int = 0
    num_xfails: int = 0
    num_xpasses: int = 0
    num_reruns: int = 0
    num_rerun_groups: int = 0
    num_warnings: int = 0
    num_warnings_unique: int = 0
    num_deselected: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_tests": self.num_tests,
            "num_tests_without_rerun": self.num_tests_without_rerun,
            "num_tests_total": self.num_tests_total,
            "num_passes": self.num_passes,
            "num_failures": self.num_failures,
            "num_errors": self.num_errors,
            "num_skips": self.num_skips,
            "num_xfails": self.num_xfails,
            "num_xpasses": self.num_xpasses,
            "num_reruns": self.num_reruns,
            "num_rerun_groups": self.num_rerun_groups,
            "num_warnings": self.num_warnings,
            "num_warnings_unique": self.num_warnings_unique,
            "num_deselected": self.num_deselected,
        }


@dataclass
class ReportBasedStats:
    """Stats collected directly from pytest test reports."""

    num_tests: int = 0
    num_tests_total: int = 0
    num_passes: int = 0
    num_failures: int = 0
    num_errors: int = 0
    num_skips: int = 0
    num_xfails: int = 0
    num_xpasses: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_tests": self.num_tests,
            "num_tests_total": self.num_tests_total,
            "num_passes": self.num_passes,
            "num_failures": self.num_failures,
            "num_errors": self.num_errors,
            "num_skips": self.num_skips,
            "num_xfails": self.num_xfails,
            "num_xpasses": self.num_xpasses,
        }


@dataclass
class SessionMetadata:
    """'Metadata': metadata about the test run, including system under test (SUT) identification
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
            "start_time": self.start_time,
            "stop_time": self.stop_time,
            "duration": self.duration,
            "sut_id": self.sut_id,
            "sut_type": self.sut_type,
            "sut_version": self.sut_version,
            "sut_environment": self.sut_environment,
            "sut_metadata": self.sut_metadata,
            "python_version": self.python_version,
            "os_info": self.os_info,
            "pytest_version": self.pytest_version,
            "command_line": self.command_line,
        }


@dataclass
class Results:
    """'Results': a collection of all data collected during a test run, made nicely
    consumable by pytest-oof.

    'session_metadata': metadata about the test session including timing and SUT info
    'session_stats': overall statistics for this test session
    'report_stats': statistics collected directly from pytest test reports
    'test_results': collection of TestResult objects for all tests in the test session
    'warnings': list of warning messages
    'rerun_test_groups': list of test groups that were rerun
    """

    session_metadata: SessionMetadata
    session_stats: TestSessionStats
    report_stats: ReportBasedStats
    test_results: List[TestResult]
    warnings: List[str] = field(default_factory=list)
    rerun_test_groups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_metadata": self.session_metadata.to_dict(),
            "session_stats": self.session_stats.to_dict(),
            "report_stats": self.report_stats.to_dict(),
            "test_results": [r.to_dict() for r in self.test_results],
            "warnings": self.warnings,
            "rerun_test_groups": self.rerun_test_groups,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Results":
        session_metadata = SessionMetadata(**data["session_metadata"])
        session_stats = TestSessionStats(**data["session_stats"])
        report_stats = ReportBasedStats(**data["report_stats"])
        test_results = [TestResult(**r) for r in data["test_results"]]
        warnings = data.get("warnings", [])
        rerun_test_groups = data.get("rerun_test_groups", [])
        return cls(
            session_metadata=session_metadata,
            session_stats=session_stats,
            report_stats=report_stats,
            test_results=test_results,
            warnings=warnings,
            rerun_test_groups=rerun_test_groups,
        )
