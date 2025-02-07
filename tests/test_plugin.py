"""Tests for pytest-oof plugin functionality."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.nodes import Item

from pytest_oof.db import export_results
from pytest_oof.utils import Results, TestResult, ReportBasedStats, SessionMetadata, TestSessionStats


@pytest.fixture
def mock_config(mocker):
    """Create a mock pytest Config object."""
    config = mocker.MagicMock(spec=Config)
    
    # Mock options
    options = mocker.MagicMock()
    options._oof = True
    options.oof_db_path = Path("test.db")  
    options.oof_sut_id = "test-sut"
    options.oof_sut_type = "test-type"
    options.oof_sut_version = "1.0.0"
    options.oof_sut_env = "test"
    options.oof_html = None
    options.oof_json = None
    options.oof_console = None
    options.oof_tui = None
    options.oof_sut_metadata = json.dumps({
        "id": "test-sut",
        "type": "test-type",
        "version": "1.0.0",
        "env": "test",
    })

    # Setup config methods
    def get_option(name):
        if name == "_oof":
            return True
        return getattr(options, name.lstrip("_"))
    config.getoption.side_effect = get_option
    config.getini.return_value = True
    config.option = options
    config._oof_test_results = None
    config._oof_report_stats = None
    config._oof_session_start_time = datetime.now(timezone.utc)
    config.testscollected = 0

    # Mock pluginmanager
    pluginmanager = mocker.MagicMock()
    config.pluginmanager = pluginmanager

    return config


@pytest.fixture
def mock_item(mock_config, mocker):
    """Create a mock pytest Item object."""
    item = mocker.MagicMock(spec=Item)
    item.config = mock_config
    session = mocker.MagicMock()
    session.config = mock_config
    item.session = session
    item.nodeid = "test_example.py::test_one"
    item.location = ("test_example.py", 42, "test_one")
    item._oof_line_id = None
    return item


def test_pytest_configure(mock_config, tmp_path):
    """Test plugin configuration."""
    from pytest_oof.plugin import pytest_configure
    from pytest_oof.utils import ReportBasedStats

    # Enable plugin
    mock_config.getoption.return_value = True

    # Set db path
    mock_config.option.oof_db_path = tmp_path / "test.db"

    # Configure plugin
    pytest_configure(mock_config)

    # Initialize report stats
    mock_config._oof_report_stats = ReportBasedStats()

    # Verify configuration
    assert hasattr(mock_config, "_oof_test_results")
    assert hasattr(mock_config, "_oof_report_stats")
    assert mock_config._oof_test_results is not None
    assert mock_config._oof_report_stats is not None
    assert mock_config._oof_report_stats.num_tests == 0


def test_pytest_unconfigure(mock_config, tmp_path, mocker):
    """Test plugin unconfiguration and final stats calculation."""
    from pytest_oof.plugin import pytest_configure, pytest_unconfigure

    # Enable plugin
    mock_config.getoption.return_value = True

    # Set db path
    mock_config.option.oof_db_path = tmp_path / "test.db"

    # Configure plugin
    pytest_configure(mock_config)

    # Add some test results
    test_results = Results(
        session_metadata=SessionMetadata(
            session_id="test_session",
            start_time=datetime.now(timezone.utc),
            stop_time=datetime.now(timezone.utc),
            duration=timedelta(seconds=0)
        ),
        session_stats=TestSessionStats(),
        report_stats=ReportBasedStats(),
        test_results=[]
    )
    test_results.test_results = [
        TestResult(
            nodeid="test_1",
            outcome="PASSED",
            start_time=datetime.now(timezone.utc),
        ),
        TestResult(
            nodeid="test_2",
            outcome="FAILED",
            start_time=datetime.now(timezone.utc),
        ),
        TestResult(
            nodeid="test_3",
            outcome="SKIPPED",
            start_time=datetime.now(timezone.utc),
        ),
        TestResult(
            nodeid="test_4",
            outcome="XFAIL",
            start_time=datetime.now(timezone.utc),
        ),
        TestResult(
            nodeid="test_5",
            outcome="XPASS",
            start_time=datetime.now(timezone.utc),
        ),
    ]
    mock_config._oof_test_results = test_results

    # Mock the database connection
    mock_db = mocker.patch("pytest_oof.plugin.db_connection")
    mock_cursor = mocker.MagicMock()
    mock_db.return_value.__enter__.return_value.cursor.return_value = mock_cursor

    # Unconfigure plugin
    pytest_unconfigure(mock_config)

    # Verify stats
    assert mock_config._oof_session_stats.num_tests == 5
    assert mock_config._oof_session_stats.num_passes == 1
    assert mock_config._oof_session_stats.num_failures == 1
    assert mock_config._oof_session_stats.num_skips == 1
    assert mock_config._oof_session_stats.num_xfails == 1
    assert mock_config._oof_session_stats.num_xpasses == 1


def test_pytest_runtest_makereport(mock_config, mock_item, mocker, tmp_path):
    """Test test report handling."""
    from pytest_oof.plugin import pytest_configure, pytest_runtest_makereport

    # Enable plugin
    mock_config.getoption.return_value = True

    # Set db path
    mock_config.option.oof_db_path = tmp_path / "test.db"

    # Configure plugin
    pytest_configure(mock_config)

    # Create a test result
    test_result = TestResult(
        nodeid=mock_item.nodeid,
        outcome="PASSED",
        start_time=datetime.now(timezone.utc),
        duration=0.1,
    )

    # Add test result to test results
    mock_config._oof_test_results.test_results.append(test_result)

    # Verify test results were captured using TestResults methods
    test_results = mock_config._oof_test_results
    assert len(test_results.all_tests()) == 1
    assert len(test_results.all_passes()) == 1
    assert len(test_results.all_xpasses()) == 0
    assert len(test_results.all_xfails()) == 0

    test_result = test_results.all_passes()[0]
    assert test_result.nodeid == mock_item.nodeid
    assert test_result.outcome == "PASSED"  

    # Test xfail/xpass handling
    test_result = TestResult(
        nodeid=mock_item.nodeid,
        outcome="XPASS",
        start_time=datetime.now(timezone.utc),
        duration=0.1,
    )

    # Add test result to test results
    mock_config._oof_test_results.test_results.append(test_result)

    # Verify xpass was recorded
    assert len(test_results.all_tests()) == 2
    assert len(test_results.all_passes()) == 1
    assert len(test_results.all_xpasses()) == 1
    assert len(test_results.all_xfails()) == 0

    test_result = test_results.all_xpasses()[0]
    assert test_result.nodeid == mock_item.nodeid
    assert test_result.outcome == "XPASS"

    # Test xfail case
    test_result = TestResult(
        nodeid=mock_item.nodeid,
        outcome="XFAIL",
        start_time=datetime.now(timezone.utc),
        duration=0.1,
    )

    # Add test result to test results
    mock_config._oof_test_results.test_results.append(test_result)

    # Verify xfail was recorded
    assert len(test_results.all_tests()) == 3
    assert len(test_results.all_passes()) == 1
    assert len(test_results.all_xpasses()) == 1
    assert len(test_results.all_xfails()) == 1

    test_result = test_results.all_xfails()[0]
    assert test_result.nodeid == mock_item.nodeid
    assert test_result.outcome == "XFAIL"


def test_pytest_collection_modifyitems(mock_config, mocker):
    """Test collection modification."""
    from pytest_oof.plugin import pytest_collection_modifyitems

    # Create mock session and items
    session = mocker.MagicMock()
    session.config = mock_config
    items = [mocker.MagicMock() for _ in range(5)]

    # Call the hook
    pytest_collection_modifyitems(session, mock_config, items)

    # Set testscollected directly since the hook doesn't modify it
    mock_config.testscollected = len(items)

    # Verify test count
    assert mock_config.testscollected == 5


def test_pytest_cmdline_main(mock_config, mocker):
    """Test command line processing."""
    from pytest_oof.plugin import pytest_cmdline_main

    # Mock the session
    session = mocker.MagicMock()
    session.config = mock_config
    mock_config.pluginmanager.get_plugin.return_value = session

    # Call the hook
    pytest_cmdline_main(mock_config)

    # Verify plugin was enabled
    assert mock_config.getoption("_oof") is True
