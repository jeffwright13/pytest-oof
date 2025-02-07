import json
import os
import platform
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pytest
from _pytest.config import Config, PytestPluginManager
from _pytest.config.argparsing import Parser
from _pytest.main import Session
from _pytest.nodes import Item
from _pytest.reports import TestReport

from pytest_oof import hooks
from pytest_oof.utils import (
    ReportBasedStats,
    Results,
    SessionMetadata,
    TestResult,
    TestSessionStats,
    generate_timestamp_uuid,
)

from .db import (
    add_session,
    add_test_result,
    db_connection,
    init_db,
    update_session_stats,
)


def pytest_addoption(parser: Parser) -> None:
    """Add pytest-oof options to pytest's command-line parser."""
    group = parser.getgroup("oof")
    group.addoption(
        "--oof",
        action="store_true",
        dest="_oof",
        default=None,
        help=(
            "Enable the pytest-oof plugin (results in files being populated/updated in /oof directory)"
        ),
    )
    group.addoption(
        "--oof-sut-id",
        action="store",
        dest="oof_sut_id",
        help="SUT (system under test) unique identifier",
        default="",
    )
    group.addoption(
        "--oof-sut-type",
        action="store",
        dest="oof_sut_type",
        help="Type/category of the system under test",
        default="",
    )
    group.addoption(
        "--oof-sut-version",
        action="store",
        dest="oof_sut_version",
        help="Version of the system under test",
        default="",
    )
    group.addoption(
        "--oof-sut-env",
        action="store",
        dest="oof_sut_env",
        help="Environment details for the system under test",
        default="",
    )
    group.addoption(
        "--oof-sut-metadata",
        action="store",
        dest="oof_sut_metadata",
        help="Additional metadata for the system under test (as JSON string)",
        default="{}",
    )
    group.addoption(
        "--oof-max-history",
        action="store",
        dest="oof_max_history",
        help="Maximum number of test runs to keep in history (default: 100, 0 for unlimited)",
        type=int,
        default=100,
    )
    group.addoption(
        "--oof-db-path",
        action="store",
        dest="oof_db_path",
        default="oof/oof-results.db",
        help="Path to SQLite database file (default: %(default)s)",
    )
    parser.addini(
        "oof",
        type="bool",
        help="Enable the pytest-oof plugin",
        default=False,
    )


def pytest_addhooks(pluginmanager: PytestPluginManager) -> None:
    """Add hooks used by pytest-oof."""
    pluginmanager.add_hookspecs(hooks.HookSpecs)


def pytest_cmdline_main(config: Config) -> None:
    """Configure command line options."""
    if hasattr(config.option, "_oof") and config.option._oof:
        config.option.verbose = 1
        config.option.reportchars = "A"


## DO NOT REMOVE !! ##
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:
    """Collect test outcomes directly from pytest reports."""
    # Get the report from the inner hook
    outcome = yield
    report = outcome.get_result()

    # Only process if plugin is enabled
    if not item.config.option._oof:
        return

    # Only process call phase or failed setup/teardown
    if report.when in ("setup", "teardown"):
        if report.outcome != "failed":
            return
        test_outcome = "ERROR"
    else:
        # Handle test phase outcomes
        if hasattr(report, "wasxfail"):
            if report.outcome in ("passed", "failed"):
                test_outcome = "XPASS"
            elif report.outcome == "skipped":
                test_outcome = "XFAIL"
            else:
                test_outcome = report.outcome.upper()
        else:
            test_outcome = report.outcome.upper()

    now = datetime.now(timezone.utc)

    # Get error details
    error_message = getattr(report, "longreprtext", "")
    error_type = str(getattr(report, "longrepr", ""))  # Convert to string
    error_traceback = getattr(report, "longreprtext", "")
    longreprtext = str(getattr(report, "longrepr", ""))  # Store full failure output

    # Get capture output
    caplog = getattr(report, "caplog", "")
    capstdout = getattr(report, "capstdout", "")
    capstderr = getattr(report, "capstderr", "")

    # Check for warnings
    has_warning = hasattr(report, "warnings") and len(report.warnings) > 0

    # Handle reruns
    is_rerun = hasattr(report, "rerun")
    rerun_count = getattr(report, "rerun", 0)

    # Create test result with rerun information
    test_result = TestResult(
        nodeid=report.nodeid,
        outcome=test_outcome,
        start_time=now,
        duration=report.duration,
        error_message=error_message,
        error_type=error_type,
        error_traceback=error_traceback,
        caplog=caplog,
        capstderr=capstderr,
        capstdout=capstdout,
        has_warning=has_warning,
        longreprtext=longreprtext,
        rerun_count=rerun_count,  # Store rerun count in test result
    )
    item.config._oof_test_results.test_results.append(test_result)

    # Update session stats based on test outcome
    stats = item.config._oof_test_results.session_stats
    
    # Update rerun stats if this is a rerun
    if is_rerun:
        stats.num_reruns += 1
        # Add test to rerun group if not already there
        rerun_group = f"{report.nodeid}::rerun_{rerun_count}"
        if rerun_group not in item.config._oof_test_results.rerun_test_groups:
            item.config._oof_test_results.rerun_test_groups.append(rerun_group)
            stats.num_rerun_groups += 1

    # Update outcome stats
    if test_outcome == "PASSED":
        stats.num_passes += 1
    elif test_outcome == "FAILED":
        stats.num_failures += 1
    elif test_outcome == "SKIPPED":
        stats.num_skips += 1
    elif test_outcome == "XFAIL":
        stats.num_xfails += 1
    elif test_outcome == "XPASS":
        stats.num_xpasses += 1
    elif test_outcome == "ERROR":
        stats.num_errors += 1

    # Update database
    with db_connection(item.config.option.oof_db_path) as conn:
        test_result = TestResult(
            nodeid=report.nodeid,
            outcome=test_outcome,
            start_time=now,
            duration=report.duration,
            error_message=error_message,
            error_type=error_type,
            error_traceback=error_traceback,
            caplog=caplog,
            capstderr=capstderr,
            capstdout=capstdout,
            has_warning=has_warning,
            longreprtext=longreprtext,
            rerun_count=0  # This will be updated by the rerunfailures plugin if needed
        )
        add_test_result(
            db_path=item.config.option.oof_db_path,
            session_id=item.config._oof_test_results.session_metadata.db_session_id,
            test_result=test_result
        )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    session: pytest.Session, config: Config, items: List[pytest.Item]
) -> None:
    """Initialize test counts after collection."""
    if not hasattr(config, "_oof_session_stats"):
        config._oof_session_stats = TestSessionStats()

    # Set initial counts
    config._oof_session_stats.num_tests_total = session.testscollected
    config._oof_session_stats.num_tests_without_rerun = len(items)
    config._oof_session_stats.num_deselected = session.testscollected - len(items)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: Config) -> None:
    """Configure pytest-oof plugin."""
    if not hasattr(config.option, "_oof"):
        config.option._oof = False

    config.addinivalue_line("markers", "oof: mark test to run with pytest-oof plugin")

    if config.getoption("--oof"):
        config.option._oof = True
        config.option.oof_db_path = Path(config.getoption("--oof-db-path"))
        init_db(config.option.oof_db_path)

        # Initialize test results container with all required metadata
        start_time = datetime.now(timezone.utc)
        session_id = str(uuid.uuid4())

        # Initialize session stats
        config._oof_session_stats = TestSessionStats(
            num_tests=0,
            num_tests_without_rerun=0,
            num_tests_total=0,
            num_passes=0,
            num_failures=0,
            num_errors=0,
            num_skips=0,
            num_xfails=0,
            num_xpasses=0,
            num_reruns=0,
            num_rerun_groups=0,
            num_warnings=0,
            num_warnings_unique=0,
            num_deselected=0
        )

        session_metadata = SessionMetadata(
            session_id=session_id,
            start_time=start_time,
            stop_time=start_time,  # Will be updated in pytest_unconfigure
            duration=timedelta(0),  # Will be updated in pytest_unconfigure
            python_version=platform.python_version(),
            os_info=platform.platform(),
            pytest_version=pytest.__version__,
            command_line=" ".join(sys.argv[1:]),
            sut_id=config.getoption("--oof-sut-id") or "",
            sut_type=config.getoption("--oof-sut-type") or "",
            sut_version=config.getoption("--oof-sut-version") or "",
            sut_environment=config.getoption("--oof-sut-env") or "",
        )

        # Create session in database first
        db_session_id = add_session(
            db_path=config.option.oof_db_path,
            start_time=start_time,
            session_id=session_id,
            sut_id=session_metadata.sut_id,
            sut_type=session_metadata.sut_type,
            sut_version=session_metadata.sut_version,
            sut_env=session_metadata.sut_environment,
        )

        # Store database session ID for later use
        session_metadata.db_session_id = db_session_id

        # Create full Results object
        config._oof_test_results = Results(
            session_metadata=session_metadata,
            session_stats=config._oof_session_stats,  # Use the initialized stats
            report_stats=ReportBasedStats(),
            test_results=[],
            rerun_test_groups=[],  # Initialize rerun test groups
        )


def pytest_unconfigure(config: Config) -> None:
    """Clean up pytest-oof plugin."""
    if not config.option._oof:
        return

    if hasattr(config, "_oof_test_results"):
        stop_time = datetime.now(timezone.utc)
        duration = stop_time - config._oof_test_results.session_metadata.start_time

        # Update session metadata with final timing
        config._oof_test_results.session_metadata.stop_time = stop_time
        config._oof_test_results.session_metadata.duration = duration

        # Update session stats in database
        with db_connection(config.option.oof_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE test_sessions SET
                    stop_time = ?,
                    duration = ?
                WHERE id = ?
                """,
                (
                    stop_time.isoformat(),
                    duration.total_seconds(),
                    config._oof_test_results.session_metadata.db_session_id,
                ),
            )
            conn.commit()

        # Update final session stats
        update_session_stats(
            db_path=config.option.oof_db_path,
            session_id=config._oof_test_results.session_metadata.db_session_id,
            stats=config._oof_session_stats,
            rerun_groups=config._oof_test_results.rerun_test_groups
        )
