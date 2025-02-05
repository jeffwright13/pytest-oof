import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import sys
import platform

import pytest
from _pytest.config import Config, PytestPluginManager
from _pytest.config.argparsing import Parser
from _pytest.main import Session
from _pytest.nodes import Item
from _pytest.reports import TestReport

from pytest_oof import hooks
from pytest_oof.utils import (
    Results,
    SessionMetadata,
    TestSessionStats,
    TestResult,
    ReportBasedStats,
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


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:
    """Collect test outcomes directly from pytest reports."""
    if not item.config.option._oof:
        yield
        return

    # Get the report
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        now = datetime.now(timezone.utc)
        
        # Get error details
        error_message = getattr(report, "longreprtext", "")
        error_type = str(getattr(report, "longrepr", ""))  # Convert to string
        error_traceback = getattr(report, "longreprtext", "")
        
        test_result = TestResult(
            nodeid=report.nodeid,
            outcome=report.outcome.upper(),
            start_time=now,
            duration=report.duration,
            error_message=error_message,
            error_type=error_type,
            error_traceback=error_traceback,
        )
        item.config._oof_test_results.test_results.append(test_result)

        # Update session stats based on test outcome
        if report.outcome == "passed":
            item.config._oof_test_results.session_stats.num_passes += 1
        elif report.outcome == "failed":
            item.config._oof_test_results.session_stats.num_failures += 1
        elif report.outcome == "skipped":
            item.config._oof_test_results.session_stats.num_skips += 1
        elif report.outcome == "xfailed":
            item.config._oof_test_results.session_stats.num_xfails += 1
        elif report.outcome == "xpassed":
            item.config._oof_test_results.session_stats.num_xpasses += 1
        elif report.outcome == "error":
            item.config._oof_test_results.session_stats.num_errors += 1

        # Update database
        with db_connection(item.config.option.oof_db_path) as conn:
            add_test_result(
                db_path=item.config.option.oof_db_path,
                session_id=item.config._oof_test_results.session_metadata.db_session_id,
                test_id=report.nodeid,
                outcome=report.outcome.upper(),
                timestamp=now,
                duration=report.duration,
                error_message=error_message,
                error_type=error_type,
                error_traceback=error_traceback,
                has_warning=False
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

        # Initialize test results container
        start_time = datetime.now(timezone.utc)
        session_id = str(uuid.uuid4())

        # Add session to database
        with db_connection(config.option.oof_db_path) as conn:
            db_session_id = add_session(
                db_path=config.option.oof_db_path,
                start_time=start_time,
                session_id=session_id
            )

        config._oof_test_results = Results(
            session_metadata=SessionMetadata(
                session_id=session_id,
                start_time=start_time,
                stop_time=start_time,  # Will be updated in pytest_unconfigure
                duration=timedelta(0),  # Will be updated in pytest_unconfigure
                python_version=platform.python_version(),
                os_info=platform.platform(),
                pytest_version=pytest.__version__,
                command_line=" ".join(sys.argv[1:])
            ),
            session_stats=TestSessionStats(),
            report_stats=ReportBasedStats(),
            test_results=[]
        )
        
        # Store database session ID for later use
        config._oof_test_results.session_metadata.db_session_id = db_session_id


def pytest_unconfigure(config: Config) -> None:
    """Clean up pytest-oof plugin."""
    if not config.option._oof:
        return

    if hasattr(config, "_oof_test_results"):
        stop_time = datetime.now(timezone.utc)
        config._oof_test_results.session_metadata.stop_time = stop_time
        config._oof_test_results.session_metadata.duration = (
            stop_time - config._oof_test_results.session_metadata.start_time
        )
        
        # Update final session stats in database
        with db_connection(config.option.oof_db_path) as conn:
            update_session_stats(
                db_path=config.option.oof_db_path,
                session_id=config._oof_test_results.session_metadata.db_session_id
            )
