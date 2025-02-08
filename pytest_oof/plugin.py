"""pytest-oof plugin."""
import os
import sys
from pathlib import Path
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

import pytest
from _pytest.config import Config, PytestPluginManager
from _pytest.config.argparsing import Parser
from _pytest.fixtures import FixtureRequest
from _pytest.main import Session
from _pytest.nodes import Item
from _pytest.reports import TestReport
from _pytest.runner import CallInfo

from pytest_oof import hooks
from pytest_oof.db import init_db, DBClient, init_sqlite_db
from pytest_oof.models import (
    TestResult,
    TestSessionStats,
    TestSession
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
        help="SUT (system under test) unique identifier (required)",
        required=True,
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


@pytest.fixture(scope="session")
def db_client(request):
    db_path = Path(request.config.getoption("--oof-db-path"))
    os.makedirs(db_path.parent, exist_ok=True)
    init_sqlite_db(db_path)
    session = init_db(str(db_path))
    yield DBClient(session)
    session.close()


## DO NOT REMOVE !! ##
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: CallInfo) -> TestReport:
    """Create a TestReport for the given test item and call."""
    outcome = yield
    report = outcome.get_result()

    try:
        if not item.config.getoption("--oof"):
            return report

        # Create test result
        test_id = item.nodeid
        result = TestResult(
            test_id=test_id,
            outcome=report.outcome,
            duration=call.duration if hasattr(call, "duration") else 0.0,
            rerun_count=getattr(item, '_oof_rerun_count', 0),
            error_data=getattr(call, 'excinfo', None),
            warnings=getattr(item, '_oof_warnings', []),
            environment={}
        )

        # Update test session stats
        stats = item.config._oof_session_stats
        if report.when == "call":
            if report.outcome == "passed":
                stats.num_passed += 1
            elif report.outcome == "failed":
                stats.num_failed += 1
            elif report.outcome == "skipped":
                stats.num_skipped += 1
            elif report.outcome == "xfailed":
                stats.num_xfailed += 1
            elif report.outcome == "xpassed":
                stats.num_xpassed += 1

        # Save test result
        try:
            db_client = item.config._oof_db_client
            db_client.add_test_result(result, item.config._oof_session_id)
        except Exception as e:
            print(f"Error saving test result: {str(e)}", file=sys.stderr)

        item.config._oof_session_stats = stats

    except Exception as e:
        print(f"Error in pytest_runtest_makereport: {str(e)}", file=sys.stderr)

    return report


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
    """Configure pytest."""
    if not config.getoption("--oof"):
        return

    try:
        # Initialize database schema
        from pytest_oof.db import init_db, init_sqlite_db
        db_path = Path(config.getoption("--oof-db-path"))
        os.makedirs(db_path.parent, exist_ok=True)
        init_sqlite_db(db_path)

        # Initialize database client
        session = init_db(str(db_path))
        db_client = DBClient(session)
        config._oof_db_client = db_client

        # Initialize session stats
        config._oof_session_stats = TestSessionStats(
            num_passed=0,
            num_failed=0,
            num_skipped=0,
            num_xfailed=0,
            num_xpassed=0,
            num_warnings=0,
            num_errors=0,
            num_rerun=0
        )

        # Store session start time
        config._oof_start_time = datetime.now(timezone.utc)

        # Create session
        config._oof_session_id = str(uuid.uuid4())
        config._oof_rerun_groups = []

        session_result = TestSession(
            session_id=config._oof_session_id,
            sut_id=config.getoption("--oof-sut-id"),
            start_time=config._oof_start_time,
            end_time=None,
            duration=None,
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            xfailed_tests=0,
            xpassed_tests=0,
            warnings=0,
            errors=0,
            rerun=0
        )
        db_client.add_session(session_result)

    except Exception as e:
        print(f"Error configuring pytest-oof: {str(e)}", file=sys.stderr)
        raise


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: Session, exitstatus: int) -> None:
    """Called after whole test run finished, right before returning the exit status to the system.
    
    Args:
        session: The pytest session object
        exitstatus: The status which pytest will return to the system
    """
    if not session.config.getoption("--oof"):
        return

    try:
        end_time = datetime.now(timezone.utc)
        duration = end_time - session.config._oof_start_time

        # Update session stats
        stats = session.config._oof_session_stats
        stats.end_time = end_time
        stats.duration = duration
        db_client = session.config._oof_db_client
        
        # Update session with final stats
        db_client.update_session_stats(
            session_id=session.config._oof_session_id,
            stats=stats
        )

    except Exception as e:
        print(f"Error in pytest_sessionfinish: {str(e)}", file=sys.stderr)


def pytest_unconfigure(config: Config) -> None:
    """Called before test process is exited."""
    if not config.getoption("--oof"):
        return

    try:
        db_client = config.pluginmanager.get_plugin('db_client')
        if db_client:
            # Get session stats from config
            session_stats = config._oof_session_stats
            
            # Update session stats in database
            try:
                db_client.update_session_stats(
                    session_id=config._oof_session_id,
                    stats=session_stats
                )
            except Exception as e:
                print(f"Error updating session stats during unconfigure: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error updating session stats during unconfigure: {e}", file=sys.stderr)
