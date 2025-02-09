"""Pytest plugin for outputting test results to a file."""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.main import Session
from _pytest.nodes import Item
from _pytest.reports import TestReport

from pytest_oof.db import (
    add_session,
    add_test_result,
    db_connection,
    export_results,
    init_db,
    update_session_stats,
)
from pytest_oof.models import TestResult, TestSessionStats, Results, SessionMetadata
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
    db_path = Path(config.option.oof_db_path or "test_results.db")
    init_db(db_path)

    # Initialize test results
    config._oof_test_results = Results(
        session_metadata=SessionMetadata(
            session_id=str(config.rootpath),
            sut_id=config.option.oof_sut_id,
            start_time=datetime.now(timezone.utc),
            stop_time=None,
            duration=None,
        ),
        session_stats=TestSessionStats(),
        report_stats=ReportBasedStats(),
        test_results=[],
    )


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

    # Add session to database
    db_path = Path(config.option.oof_db_path or "test_results.db")
    session_id = add_session(
        db_path,
        start_time=results.session_metadata.start_time,
        session_id=results.session_metadata.session_id,
        sut_id=results.session_metadata.sut_id,
    )

    # Add test results to database
    for result in results.test_results:
        add_test_result(db_path, session_id, result)

    # Update session stats
    update_session_stats(db_path, session_id, results.session_stats)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: Any) -> TestReport:
    """Process test reports."""
    outcome = yield
    report = outcome.get_result()

    if not hasattr(item.config, "_oof_test_results"):
        return report

    results = item.config._oof_test_results

    if report.when == "call" or (report.when == "setup" and report.outcome == "skipped"):
        test_result = TestResult(
            test_id=item.nodeid,
            outcome=report.outcome.upper(),
            duration=report.duration,
            error_data={
                "type": str(report.longrepr) if report.longrepr else None,
                "message": str(report.longrepr) if report.longrepr else None,
                "traceback": str(report.longrepr) if report.longrepr else None,
            } if report.longrepr else None,
            environment={},
            warnings=[],
            rerun_count=0,
        )
        results.test_results.append(test_result)

    return report


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session: Session, config: Config, items: List[Item]) -> None:
    """Initialize test session stats with collected items."""
    if not hasattr(config, "_oof_test_results"):
        return

    results = config._oof_test_results
    results.session_stats.total_tests = len(items)
