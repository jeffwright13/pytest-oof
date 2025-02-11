"""Data models for pytest-oof."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# SQLAlchemy Models
class SQLTestSession(Base):
    """SQLAlchemy model for test sessions."""

    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    sut_id = Column(String, nullable=False)
    sut_type = Column(String, nullable=True)
    sut_version = Column(String, nullable=True)
    sut_environment = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # Store duration in seconds
    total_tests = Column(Integer, default=0)
    passed_tests = Column(Integer, default=0)
    failed_tests = Column(Integer, default=0)
    skipped_tests = Column(Integer, default=0)
    xfailed_tests = Column(Integer, default=0)
    xpassed_tests = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    rerun = Column(Integer, default=0)
    rerun_outcomes = Column(JSON, default=list)

    test_results = relationship("TestResult", back_populates="session")


class TestResult(Base):
    """A test result."""

    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False)
    test_id = Column(String, nullable=False)
    outcome = Column(String, nullable=False)
    start_time = Column(DateTime)
    duration = Column(Float)
    error_message = Column(String)
    error_type = Column(String)
    error_traceback = Column(String)
    has_warning = Column(Boolean, default=False)
    longreprtext = Column(String)
    caplog = Column(String)
    capstdout = Column(String)
    capstderr = Column(String)
    rerun_count = Column(Integer, default=0)
    rerun_outcomes = Column(JSON, default=list)
    environment = Column(JSON)
    warnings = Column(JSON)

    session = relationship("SQLTestSession", back_populates="test_results")

    def __init__(
        self,
        test_id: str,
        outcome: str,
        duration: float = 0.0,
        error_data: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        rerun_count: int = 0,
        rerun_outcomes: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ):
        """Initialize a test result."""
        self.test_id = test_id
        self.outcome = outcome
        self.duration = duration
        if error_data:
            self.error_message = error_data.get("message", "")
            self.error_type = error_data.get("type", "")
            self.error_traceback = error_data.get("traceback", "")
        self.environment = environment or {}
        self.warnings = warnings or []
        self.rerun_count = rerun_count
        self.rerun_outcomes = rerun_outcomes or []
        self.session_id = session_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_id": self.test_id,
            "outcome": self.outcome,
            "duration": self.duration,
            "error_data": {
                "message": self.error_message,
                "type": self.error_type,
                "traceback": self.error_traceback,
            }
            if self.error_message
            else None,
            "environment": self.environment,
            "warnings": self.warnings,
            "rerun_count": self.rerun_count,
            "rerun_outcomes": self.rerun_outcomes,
            "session_id": self.session_id,
        }


# Dataclass Models
@dataclass
class TestSessionStats:
    """Test session statistics."""

    num_passed: int = 0
    num_failed: int = 0
    num_skipped: int = 0
    num_xfailed: int = 0
    num_xpassed: int = 0
    num_warnings: int = 0
    num_errors: int = 0
    num_rerun: int = 0
    end_time: Optional[datetime] = None
    duration: Optional[timedelta] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert TestSessionStats to a dictionary."""
        return {
            "total_tests": self.num_passed
            + self.num_failed
            + self.num_skipped
            + self.num_xfailed
            + self.num_xpassed,
            "passed_tests": self.num_passed,
            "failed_tests": self.num_failed,
            "skipped_tests": self.num_skipped,
            "xfailed_tests": self.num_xfailed,
            "xpassed_tests": self.num_xpassed,
            "warnings": self.num_warnings,
            "errors": self.num_errors,
            "rerun": self.num_rerun,
            "end_time": self.end_time,
            "duration": self.duration,
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
class TestSession:
    """Test session information."""

    session_id: str
    sut_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[timedelta] = None
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    xfailed_tests: int = 0
    xpassed_tests: int = 0
    warnings: int = 0
    errors: int = 0
    rerun: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "sut_id": self.sut_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": str(self.duration) if self.duration else None,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "xfailed_tests": self.xfailed_tests,
            "xpassed_tests": self.xpassed_tests,
            "warnings": self.warnings,
            "errors": self.errors,
            "rerun": self.rerun,
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
