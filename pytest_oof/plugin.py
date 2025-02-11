import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.main import Session
from _pytest.nodes import Item
from _pytest.reports import TestReport

from pytest_oof.db import (
    add_session,
    add_test_result,
    init_sqlite_db,
    update_session_stats,
)
from pytest_oof.models import Results, SessionMetadata, TestResult, TestSessionStats
from pytest_oof.utils import ReportBasedStats


def pytest_addoption(parser: Parser) -> None:
    """Add plugin options to pytest."""
    group = parser.getgroup("oof")
    group.addoption(
        "--oof",
        action="store_true",
        dest="oof",
        help="Enable output to file",
        default=False,
    )
    group.addoption(
        "--oof-db-path",
        action="store",
        dest="oof_db_path",
        help="Path to SQLite database file",
        default=None,
    )
    group.addoption(
        "--oof-sut-id",
        action="store",
        dest="oof_sut_id",
        help="SUT (system under test) unique identifier (required when --oof is enabled)",
        default=None,
    )


@pytest.hookimpl(trylast=True)
def pytest_configure(config: Config) -> None:
    """Configure the plugin."""
    if not config.option.oof:
        return

    if not config.option.oof_sut_id:
        raise pytest.UsageError("--oof-sut-id is required when --oof is enabled")

    # Initialize database if needed
    db_path = Path(config.option.oof_db_path or "./.oof/oof-results.db")
    init_sqlite_db(db_path)

    # Initialize test results
    session_id = str(uuid.uuid4())
    config._oof_test_results = Results(
        session_metadata=SessionMetadata(
            session_id=session_id,
            sut_id=config.option.oof_sut_id,
            start_time=datetime.now(timezone.utc),
            stop_time=None,
            duration=None,
        ),
        session_stats=TestSessionStats(
            end_time=None,
            duration=None,
        ),
        report_stats=ReportBasedStats(),
        test_results=[],
    )
    config._oof_reports = {}
    config._oof_rerun_groups = set()


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config: Config) -> None:
    """Unconfigure the plugin and write results to file."""
    if not hasattr(config, "_oof_test_results"):
        return

    results = config._oof_test_results
    results.session_metadata.stop_time = datetime.now(timezone.utc)
    results.session_metadata.duration = (
        results.session_metadata.stop_time - results.session_metadata.start_time
    )

    # Update session stats with timing information
    results.session_stats.end_time = results.session_metadata.stop_time
    results.session_stats.duration = results.session_metadata.duration

    # Add session to database
    db_path = Path(config.option.oof_db_path or "./.oof/oof-results.db")
    session_id = add_session(
        db_path,
        start_time=results.session_metadata.start_time,
        session_id=results.session_metadata.session_id,
        sut_id=results.session_metadata.sut_id,
    )

    # Add test results to database
    for result in results.test_results:
        add_test_result(
            db_path,
            session_id,
            test_id=result.test_id,
            outcome=result.outcome,
            duration=result.duration,
            error_data=getattr(result, "error_data", None),
            environment=result.environment,
            warnings=result.warnings,
            rerun_count=result.rerun_count,
        )

    # Update session stats with rerun groups
    list(getattr(config, "_oof_rerun_groups", set()))
    update_session_stats(db_path, session_id)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: Any) -> TestReport:
    """Process test reports."""
    outcome = yield
    report = outcome.get_result()

    if not item.config.option.oof:
        return report

    # Initialize reports dict for this test if needed
    if item.nodeid not in item.config._oof_reports:
        item.config._oof_reports[item.nodeid] = {}

    # Store report by (when, outcome) tuple
    key = (report.when, report.outcome)
    if report.outcome == "rerun":
        # For reruns, store all attempts
        if key not in item.config._oof_reports[item.nodeid]:
            item.config._oof_reports[item.nodeid][key] = []
        item.config._oof_reports[item.nodeid][key].append(report)
    else:
        # For non-reruns, store only the latest
        item.config._oof_reports[item.nodeid][key] = report

    # Only process final results after teardown (unless it's a rerun)
    if report.when == "teardown" and report.outcome != "rerun":
        process_test_result(item, item.config._oof_reports[item.nodeid])

    return report


def process_test_result(item, reports):
    """Process all reports for a test and add the final result."""
    # Get the call report (or setup for skips) - prioritize xfail/xpass
    call = (
        reports.get(("call", "xfailed"))  # Check xfail first
        or reports.get(("call", "xpassed"))  # Then xpass
        or reports.get(("call", "passed"))
        or reports.get(("call", "failed"))
        or reports.get(("call", "skipped"))
        or reports.get(("setup", "skipped"))
    )

    if not call:
        return

    # Count reruns and collect outcomes
    rerun_reports = []
    rerun_outcomes = []
    for key, report in reports.items():
        if key[1] == "rerun":
            if isinstance(report, list):
                rerun_reports.extend(report)
                rerun_outcomes.extend([r.outcome.upper() for r in report])
            else:
                rerun_reports.append(report)
                rerun_outcomes.append(report.outcome.upper())

    if rerun_reports:
        # Add to rerun groups if there were reruns
        item.config._oof_rerun_groups.add(item.nodeid)

    test_result = TestResult(
        test_id=item.nodeid,
        outcome=call.outcome.lower(),  # Convert to lowercase
        duration=call.duration,
        error_data={
            "type": str(call.longrepr) if call.longrepr else None,
            "message": str(call.longrepr) if call.longrepr else None,
            "traceback": str(call.longrepr) if call.longrepr else None,
        }
        if call.longrepr
        else None,
        environment={},
        warnings=[],
        rerun_count=len(rerun_reports),
        rerun_outcomes=[
            outcome.lower() for outcome in rerun_outcomes
        ],  # Convert to lowercase
    )

    item.config._oof_test_results.test_results.append(test_result)

    # Update session stats
    stats = item.config._oof_test_results.session_stats
    if call.outcome == "passed":
        stats.num_passed += 1
    elif call.outcome == "failed":
        stats.num_failed += 1
    elif call.outcome == "skipped":
        stats.num_skipped += 1
    elif call.outcome == "xfailed":
        stats.num_xfailed += 1
    elif call.outcome == "xpassed":
        stats.num_xpassed += 1
    if call.longrepr:
        stats.num_errors += 1
    if rerun_reports:
        stats.num_rerun += 1


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    session: Session, config: Config, items: List[Item]
) -> None:
    """Initialize test session stats with collected items."""
    if not hasattr(config, "_oof_test_results"):
        return

    results = config._oof_test_results
    if results.session_stats is None:
        results.session_stats = TestSessionStats()

    # Manually set total tests
    results.session_stats.num_passed = 0
    results.session_stats.num_failed = 0
    results.session_stats.num_skipped = 0
    results.session_stats.num_xfailed = 0
    results.session_stats.num_xpassed = 0


def pytest_cmdline_main(config: Config) -> Optional[int]:
    """Process command line options.

    Args:
        config: Pytest configuration object.

    Returns:
        Optional exit code.
    """
    # Placeholder implementation
    return None
