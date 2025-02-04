import json
import pickle
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest
from _pytest._io.terminalwriter import TerminalWriter
from _pytest.config import Config, PytestPluginManager, create_terminal_writer
from _pytest.config.argparsing import Parser
from _pytest.reports import TestReport
from strip_ansi import strip_ansi

from pytest_oof import hooks
from pytest_oof.utils import (
    HISTORY_FILE,
    JSON_OUT_FILE,
    RESULTS_FILE,
    OutputField,
    OutputFields,
    ReportBasedStats,
    RerunTestGroup,
    Results,
    SessionMetadata,
    TestHistory,
    TestResult,
    TestResults,
    TestSessionStats,
    generate_timestamp_uuid,
)

# regex matching patterns for pytest console output fields/sections
test_session_starts_field_matcher = re.compile(r"^==.*\stest session starts\s==+")
test_session_starts_results_grabber = re.compile(r"(collected\s\d+\sitems[\s\S]+)")
test_session_starts_test_matcher = r"^(.*::.*)"
errors_field_matcher = re.compile(r"^==.*\sERRORS\s==+")
failures_field_matcher = re.compile(r"^==.*\sFAILURES\s==+")
warnings_summary_field_matcher = re.compile(r"^==.*\swarnings summary\s.*==+")
passes_field_matcher = re.compile(r"^==.*\sPASSES\s==+")
rerun_test_summary_field_matcher = re.compile(r"^==.*\srerun test summary info\s.*==+")
short_test_summary_field_matcher = re.compile(r"^==.*\sshort test summary info\s.*==+")
short_test_summary_test_matcher = re.compile(
    r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS|RERUN)\s+(?:\[\d+\]\s)?(\S+)(?:.*)?$"
)
# warnings_summary_test_matcher = re.compile(r"^([^\n]+:{1,2}[^\n]+)\n([^\n]+\n)+")
warnings_summary_test_matcher = re.compile(r"^[\w\/-]+\.py:+:*\w+")

lastline_matcher = re.compile(r"^==.*in\s\d+.\d+s.*=+")
standard_test_matcher = re.compile(
    r"(.*\::\S+)\s(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS|RERUN)"
)
# nodeid_matcher = re.compile(r"([\w/.]+::[\w/]+(?:\[[^\]]+\])?)")


@dataclass
class ResultsFromConfig(Results):
    """
    Creates a Results object from a pytest Config object.
    This is used during test execution to collect results.
    """

    def __init__(self):
        super().__init__(
            session_metadata=SessionMetadata(
                session_id=generate_timestamp_uuid(),
                start_time=datetime.now(timezone.utc),
                stop_time=datetime.now(timezone.utc),
                duration=timedelta(0),
                sut_id="",
                sut_type="",
                sut_version="",
                sut_environment="",
                sut_metadata={},
            ),
            session_stats=TestSessionStats(),
            report_stats=ReportBasedStats(),
            test_results=[],
            output_fields=OutputFields(),
            warnings=[],
            rerun_test_groups=[],
        )

    @classmethod
    def from_config(cls, config: Config) -> "ResultsFromConfig":
        """Create a Results object from a pytest Config object."""
        instance = cls()
        instance.session_metadata = SessionMetadata(
            session_id=getattr(config, "_oof_session_id", generate_timestamp_uuid()),
            start_time=getattr(config, "_oof_session_start_time", datetime.now(timezone.utc)),
            stop_time=getattr(config, "_oof_session_stop_time", datetime.now(timezone.utc)),
            duration=getattr(config, "_oof_session_duration", timedelta(0)),
            sut_id=getattr(config, "_oof_sut_id", ""),
            sut_type=getattr(config, "_oof_sut_type", ""),
            sut_version=getattr(config, "_oof_sut_version", ""),
            sut_environment=getattr(config, "_oof_sut_environment", ""),
            sut_metadata=getattr(config, "_oof_sut_metadata", {}),
        )

        if not hasattr(config, "_oof_report_stats"):
            config._oof_report_stats = ReportBasedStats()
            # Initialize total test count including deselected
            config._oof_report_stats.num_tests_total = (
                config._oof_session_stats.num_tests_total
            )

        instance.session_stats = config._oof_session_stats
        instance.report_stats = config._oof_report_stats
        instance.test_results = config._oof_test_results.test_results
        instance.output_fields = config._oof_fields
        instance.warnings = config._oof_test_results.all_warnings()
        instance.rerun_test_groups = config._oof_rerun_test_groups

        return instance


def pytest_addoption(parser: Parser) -> None:
    group = parser.getgroup("oof")
    group.addoption(
        "--oof",
        action="store_true",
        dest="_oof",
        default=None,
        help=("Enable the pytest-oof plugin (reults in files being populated/updated in /oof directory)"),
    )
    group.addoption(
        "--oof-sut-id",
        action="store",
        dest="oof_sut_id",
        help="SUT (system under test) unique identifier",
        default=""
    )
    group.addoption(
        "--oof-sut-type",
        action="store",
        dest="oof_sut_type",
        help="Type/category of the system under test",
        default=""
    )
    group.addoption(
        "--oof-sut-version",
        action="store",
        dest="oof_sut_version",
        help="Version of the system under test",
        default=""
    )
    group.addoption(
        "--oof-sut-env",
        action="store",
        dest="oof_sut_env",
        help="Environment details for the system under test",
        default=""
    )
    group.addoption(
        "--oof-sut-metadata",
        action="store",
        dest="oof_sut_metadata",
        help="Additional metadata for the system under test (as JSON string)",
        default="{}"
    )
    group.addoption(
        "--oof-max-history",
        action="store",
        dest="oof_max_history",
        help="Maximum number of test runs to keep in history (default: 100, 0 for unlimited)",
        type=int,
        default=100
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


def add_ansi_to_report(config: Config, report: TestReport) -> None:
    """
    If the report has longreprtext (traceback info), mark it up with ANSI codes
    From https://stackoverflow.com/questions/71846269/algorithm-for-extracting-first-and-last-lines-from-fieldalized-output-file
    """
    buf = StringIO()
    buf.isatty = lambda: True

    reporter = config.pluginmanager.getplugin("terminalreporter")
    original_writer = reporter._tw
    writer = create_terminal_writer(config, file=buf)
    reporter._tw = writer

    reporter._outrep_summary(report)
    buf.seek(0)
    ansi = buf.read()
    buf.close()

    report.ansi = SimpleNamespace()
    setattr(report.ansi, "val", ansi)

    reporter._tw = original_writer


def replace_string(original_string, new_char, new_phrase):
    """Replace a phrase in a string with a new phrase, padding with a new character."""
    parts = original_string.split(" ")

    old_phrase_length = len(parts[1])
    new_phrase_length = len(new_phrase)
    length_difference = old_phrase_length - new_phrase_length
    char_count = len(parts[0]) + length_difference // 2

    if length_difference % 2 != 0:
        return f"{new_char * char_count} {new_phrase} {new_char * (char_count + 1)}"
    else:
        return f"{new_char * char_count} {new_phrase} {new_char * char_count}"


def pytest_cmdline_main(config: Config) -> None:
    # If the oof option is enabled, put the OOF plugin in verbose mode,
    # and force all test results to be reported, including reruns.
    # Verbose (makes final outcome classification possible)
    # Reportchars = RA (forces All test results, plus Reruns)
    if hasattr(config.option, "_oof") and config.option._oof:
        config.option.verbose = 1
        config.option.reportchars = "A"
        if hasattr(config.option, "reruns"):
            config.option.reportchars += "R"

    # Using global Config object to store OOF-specific attributes.
    # TODO: port to Stash in future; but that will break backwards compatibility
    # for pytest < 7.0.
    if not hasattr(config, "_oof_session_start_time"):
        config._oof_session_start_time = datetime.now(timezone.utc)
    if not hasattr(config, "_oof_session_id"):
        config._oof_session_id = generate_timestamp_uuid()
    if not hasattr(config, "_oof_metadata"):
        config._oof_metadata = {
            "session_id": config._oof_session_id,
            "start_time": None,  # Will be set when the session starts
            "stop_time": None,  # Will be set when the session ends
            "duration": None,  # Will be calculated later
        }
    if not hasattr(config, "_oof_sessionstart"):
        config._oof_sessionstart = True
    if not hasattr(config, "_oof_sessionstart_test_outcome_next"):
        config._oof_sessionstart_test_outcome_next = False
    if not hasattr(config, "_oof_sessionstart_current_nodeid"):
        config._oof_sessionstart_current_nodeid = ""
    if not hasattr(config, "_oof_session_stats"):
        config._oof_session_stats = TestSessionStats()
    if not hasattr(config, "_oof_rerun_test_groups"):
        config._oof_rerun_test_groups = []
    if not hasattr(config, "_oof_current_rerun_test_group"):
        config._oof_current_rerun_test_group = 0
    if not hasattr(config, "_oof_current_field"):
        config._oof_current_field = "pre_test"
    if not hasattr(config, "_oof_reports"):
        config._oof_reports = []
    if not hasattr(config, "_oof_test_results"):
        config._oof_test_results = TestResults()
    if not hasattr(config, "_oof_terminal_out"):
        config._oof_terminal_out = tempfile.TemporaryFile("wb+")
    if not hasattr(config, "_oof_fields"):
        config._oof_fields = OutputFields(
            test_session_starts=OutputField(name="test_session_starts", content=""),
            errors=OutputField(name="errors", content=""),
            failures=OutputField(name="failures", content=""),
            passes=OutputField(name="passes", content=""),
            warnings_summary=OutputField(name="warnings_summary", content=""),
            rerun_test_summary=OutputField(name="rerun_test_summary", content=""),
            short_test_summary=OutputField(name="short_test_summary", content=""),
            lastline=OutputField(name="lastline", content=""),
        )


def pytest_report_teststatus(report: TestReport, config: Config) -> None:
    if not hasattr(config.option, "_oof"):
        return
    if not config.option._oof:
        return

    # Instantiate TerminalWriter to write separation strings for captured stdout,
    # stderr and stdlog. These are appended to the TuiTestResult's capstdout,
    # captstderr and caplog attrs to replicate terminal output.
    # Don't do this for longreptext, as it is already included there.
    caplog_sep = (
        replace_string(config._oof_test_session_starts_line, "-", "Captured log call")
        + "\n"
    )
    capstderr_sep = (
        replace_string(
            config._oof_test_session_starts_line, "-", "Captured stderr call"
        )
        + "\n"
    )
    capstdout_sep = (
        replace_string(
            config._oof_test_session_starts_line, "-", "Captured stdout call"
        )
        + "\n"
    )

    if hasattr(report, "caplog") and report.caplog:
        for oof_test_result in config._oof_test_results.test_results:
            if oof_test_result.nodeid == report.nodeid:
                oof_test_result.caplog = caplog_sep + report.caplog + "\n"

    if hasattr(report, "capstderr") and report.capstderr:
        for oof_test_result in config._oof_test_results.test_results:
            if oof_test_result.nodeid == report.nodeid:
                oof_test_result.capstderr = capstderr_sep + report.capstderr

    if hasattr(report, "capstdout") and report.capstdout:
        for oof_test_result in config._oof_test_results.test_results:
            if oof_test_result.nodeid == report.nodeid:
                oof_test_result.capstdout = capstdout_sep + report.capstdout

    if hasattr(report, "longreprtext") and report.longreprtext:
        add_ansi_to_report(config, report)
        for oof_test_result in config._oof_test_results.test_results:
            if oof_test_result.nodeid == report.nodeid:
                oof_test_result.longreprtext = report.ansi.val
                oof_test_result.longreprtext_stripped = oof_test_result.longreprtext

    if hasattr(report, "longreprtext") and report.longreprtext:
        add_ansi_to_report(config, report)
        for oof_test_result in config._oof_test_results.test_results:
            if oof_test_result.nodeid == report.nodeid:
                oof_test_result.longreprtext = report.ansi.val

    config._oof_reports.append(report)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:
    """Collect test outcomes directly from pytest reports."""
    # Get or create the report-based stats
    if not hasattr(item.session.config, "_oof_report_stats"):
        item.session.config._oof_report_stats = ReportBasedStats()
        # Initialize total test count including deselected
        item.session.config._oof_report_stats.num_tests_total = (
            item.session.testscollected
        )

    if not hasattr(item.session.config, "_oof_test_results"):
        item.session.config._oof_test_results = TestResults()

    report_stats = item.session.config._oof_report_stats
    test_results = item.session.config._oof_test_results

    # Get the report
    outcome = yield
    report = outcome.get_result()

    # Only process the call phase for counting test outcomes
    if report.when == "call":
        report_stats.num_tests += 1  # Total runs including reruns

        # Create a TestResult object
        test_result = TestResult(
            nodeid=report.nodeid,
            outcome=report.outcome,
            duration=report.duration,
            longreprtext=report.longrepr if hasattr(report, 'longrepr') else None,
            capstdout=report.capstdout if hasattr(report, 'capstdout') else "",
            capstderr=report.capstderr if hasattr(report, 'capstderr') else "",
            caplog=report.caplog if hasattr(report, 'caplog') else "",
            has_warning=False,
            start_time=datetime.now(timezone.utc),
            longreprtext_stripped=strip_ansi(str(report.longrepr)) if hasattr(report, 'longrepr') else None,
        )
        test_results.test_results.append(test_result)

        # Handle xfail/xpass cases
        if hasattr(report, "wasxfail"):
            if report.outcome in ("passed", "failed"):
                report_stats.num_xpasses += 1
            elif report.outcome == "skipped":
                report_stats.num_xfails += 1
        # Handle normal outcomes
        else:
            if report.outcome == "passed":
                report_stats.num_passes += 1
            elif report.outcome == "failed":
                report_stats.num_failures += 1
            elif report.outcome == "skipped":
                report_stats.num_skips += 1

    # Handle setup/teardown errors
    elif report.when in ("setup", "teardown") and report.outcome == "failed":
        report_stats.num_errors += 1


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
    """
    Configure pytest-oof plugin, including setting up hooks and initializing data structures.
    """
    # Check if plugin is enabled via command line option or ini file
    enabled = config.getoption("_oof")
    if enabled is None:
        enabled = config.getini("oof")
    if not enabled:
        return

    # Get SUT-related options
    sut_id = config.getoption("oof_sut_id")
    sut_type = config.getoption("oof_sut_type")
    sut_version = config.getoption("oof_sut_version")
    sut_environment = config.getoption("oof_sut_env")
    try:
        sut_metadata = json.loads(config.getoption("oof_sut_metadata"))
    except json.JSONDecodeError:
        sut_metadata = {}

    # Initialize session data
    session_id = generate_timestamp_uuid()
    session_start_time = datetime.now(timezone.utc)
    config._oof_session_id = session_id
    config._oof_session_start_time = session_start_time
    config._oof_session_stop_time = None
    config._oof_session_duration = None

    # Store SUT information
    config._oof_sut_id = sut_id
    config._oof_sut_type = sut_type
    config._oof_sut_version = sut_version
    config._oof_sut_environment = sut_environment
    config._oof_sut_metadata = sut_metadata

    # Initialize other session data
    config._oof_session_stats = TestSessionStats()
    config._oof_test_results = TestResults()
    config._oof_fields = OutputFields()
    config._oof_rerun_test_groups = []

    # Examine Pytest terminal output to mark different fields of the output.
    # This code is based on pytest's 'pastebin.py'.
    tr = config.pluginmanager.getplugin("terminalreporter")
    if tr is not None:
        # Save the old terminal writer instance so we can restore it later
        oldwrite = tr._tw.write

        # identify and mark each results field
        def tee_write(s, **kwargs):
            # Check to see if current line is a field start marker
            if re.search(test_session_starts_field_matcher, s):
                config._oof_current_field = "test_session_starts"
                config._oof_test_session_starts_line = s
            if re.search(errors_field_matcher, s):
                config._oof_current_field = "errors"
            if re.search(failures_field_matcher, s):
                config._oof_current_field = "failures"
            if re.search(warnings_summary_field_matcher, s):
                config._oof_current_field = "warnings_summary"
            if re.search(passes_field_matcher, s):
                config._oof_current_field = "passes"
            if re.search(rerun_test_summary_field_matcher, s):
                config._oof_current_field = "rerun_test_summary"
            if re.search(short_test_summary_field_matcher, s):
                config._oof_current_field = "short_test_summary"
            if re.search(lastline_matcher, s):
                config._oof_current_field = "lastline"
            else:
                # This line is not a field start marker
                if config._oof_sessionstart:
                    config._oof_current_field = "test_session_starts"
                    config._oof_sessionstart = False

            # If this is a "collecting..." line, insert a line feed after it to prevent non-wrapped following items.
            if re.search(r"^collecting\s.*", s):
                s += "\n"

            # If this is an actual test outcome line in the initial `=== test session starts ==='
            # field, populate the TestResult's fully qualified test name field (aka nodeid).
            if config._oof_current_field == "test_session_starts":
                if config._oof_sessionstart_test_outcome_next:
                    outcome = s.strip()
                    config._oof_test_results.test_results[-1].outcome = outcome
                    # Update session stats based on the outcome
                    if outcome == "PASSED":
                        config._oof_session_stats.num_passes += 1
                    elif outcome == "FAILED":
                        config._oof_session_stats.num_failures += 1
                    elif outcome == "SKIPPED":
                        config._oof_session_stats.num_skips += 1
                    elif outcome == "XFAIL":
                        config._oof_session_stats.num_xfails += 1
                    elif outcome == "XPASS":
                        config._oof_session_stats.num_xpasses += 1
                    elif outcome == "ERROR":
                        config._oof_session_stats.num_errors += 1
                    elif outcome == "RERUN":
                        config._oof_session_stats.num_reruns += 1
                    config._oof_session_stats.num_tests += 1
                    config._oof_sessionstart_test_outcome_next = False

                search = re.search(test_session_starts_test_matcher, s, re.MULTILINE)
                if search:
                    nodeid = re.search(
                        test_session_starts_test_matcher, s, re.MULTILINE
                    )[1].rstrip()
                    config._oof_sessionstart_current_nodeid = nodeid
                    config._oof_test_results.test_results.append(
                        TestResult(nodeid=nodeid)
                    )
                    config._oof_sessionstart_test_outcome_next = True

            # If this is an actual test outcome line in the `=== short test summary info ===' field,
            # populate the TestResult's outcome attribute.
            if config._oof_current_field == "short_test_summary" and re.search(
                short_test_summary_test_matcher, strip_ansi(s)
            ):
                outcome = re.search(
                    short_test_summary_test_matcher, strip_ansi(s)
                ).groups()[0]
                nodeid = re.search(
                    short_test_summary_test_matcher, strip_ansi(s)
                ).groups()[1]

                for oof_test_result in config._oof_test_results.test_results:
                    if (
                        oof_test_result.nodeid == nodeid
                        and oof_test_result.outcome != "RERUN"
                    ):
                        oof_test_result.outcome = outcome
                        break

            # If this is the last line, parse it for deselected tests
            if config._oof_current_field == "lastline":
                lastline = strip_ansi(s)
                deselected_match = re.search(r"(\d+) deselected", lastline)
                if deselected_match:
                    config._oof_session_stats.num_deselected = int(
                        deselected_match.group(1)
                    )

            # Write this line's original pytest output text (plus markup) to console.
            # Also write marked up content to this OutputField's 'content' field.
            # Markup is done w/ TerminalWriter's 'markup' method.
            # (do not pass "flush" to the method, or it will throw an error)
            oldwrite(s, **kwargs)
            kwargs.pop("flush") if "flush" in kwargs else None

            s_orig = s
            kwargs.pop("flush") if "flush" in kwargs else None
            s_orig = TerminalWriter().markup(s, **kwargs)
            exec(f"config._oof_fields.{config._oof_current_field}.content += s_orig")
            exec(
                f"config._oof_fields.{config._oof_current_field}.content_stripped += strip_ansi(s_orig)"
            )
            if isinstance(s_orig, str):
                unmarked_up = s_orig.encode("utf-8")
            config._oof_terminal_out.write(unmarked_up)

        # Write to both terminal/console and tempfiles
        tr._tw.write = tee_write
        print()


def populate_rerun_groups(config: Config) -> List[RerunTestGroup]:
    """Build a list of RerunTestGroup objects from the test
    results in the config object."""
    rerun_test_groups = []

    # First, get all test results that have an outcome of "RERUN"
    rerun_tests = [
        test_result
        for test_result in config._oof_test_results.test_results
        if test_result.outcome == "RERUN"
    ]

    # If there are no rerun tests, return empty list
    if not rerun_tests:
        return rerun_test_groups

    # Group the rerun tests by nodeid
    rerun_tests_by_nodeid = {}
    for test_result in rerun_tests:
        if test_result.nodeid not in rerun_tests_by_nodeid:
            rerun_tests_by_nodeid[test_result.nodeid] = []
        rerun_tests_by_nodeid[test_result.nodeid].append(test_result)

    # Get unique nodeids from rerun test summary field

    # Update session stats for reruns
    config._oof_session_stats.num_reruns = len(rerun_tests)
    config._oof_session_stats.num_rerun_groups = len(rerun_tests_by_nodeid)
    config._oof_session_stats.num_tests = len(config._oof_test_results.test_results)
    config._oof_session_stats.num_tests_without_rerun = (
        config._oof_session_stats.num_tests - config._oof_session_stats.num_reruns
    )

    # Build RerunTestGroup objects
    for nodeid, rerun_tests in rerun_tests_by_nodeid.items():
        # Get all test results for this nodeid, including the final result
        all_test_results = [
            test_result
            for test_result in config._oof_test_results.test_results
            if test_result.nodeid == nodeid
        ]

        # The final test is the last one that's not a RERUN
        final_test = next(
            (test for test in reversed(all_test_results) if test.outcome != "RERUN"),
            None,
        )

        if final_test:
            rerun_test_groups.append(
                RerunTestGroup(
                    nodeid=nodeid,
                    final_outcome=final_test.outcome,
                    final_test=final_test,
                    forerunners=rerun_tests,
                    full_test_list=all_test_results,
                )
            )

    return rerun_test_groups


def mark_warning_tests(config: Config) -> List[TestResult]:
    """Mark tests that have warnings in the warnings field."""
    warning_field = strip_ansi(config._oof_fields.warnings_summary.content)
    warning_field_lines = warning_field.split("\n")

    # use regex warnings_summary_test_matcher to match the nodeids in the warning field
    # to the config test results in the test_results list
    warning_nodeids = []
    for line in warning_field_lines:
        if re.search(warnings_summary_test_matcher, line):
            warning_nodeids.append(line)

    # Update warning counts
    config._oof_session_stats.num_warnings = len(warning_nodeids)
    config._oof_session_stats.num_warnings_unique = len(set(warning_nodeids))

    for test_result in config._oof_test_results.test_results:
        for warning_nodeid in warning_nodeids:
            if test_result.nodeid == warning_nodeid:
                test_result.has_warning = True

    return warning_nodeids


def pytest_unconfigure(config: Config) -> None:
    """
    Called before test process is exited.
    """
    if not hasattr(config, "_oof_session_id"):
        return

    if not config.getoption("_oof"):
        return

    # Calculate session duration
    config._oof_session_stop_time = datetime.now(timezone.utc)
    config._oof_session_duration = (
        config._oof_session_stop_time - config._oof_session_start_time
    )

    # Process rerun groups and warnings
    config._oof_rerun_test_groups = populate_rerun_groups(config)
    mark_warning_tests(config)

    # Create Results object
    results = ResultsFromConfig.from_config(config)

    # Save individual results
    with open(RESULTS_FILE, "wb") as f:
        pickle.dump(results, f)

    # Convert to JSON
    json_results = results.to_dict()

    # Load and update JSON history
    json_history_file = Path("oof/oof-results.json")
    existing_results = []
    
    if json_history_file.exists():
        try:
            with open(json_history_file) as f:
                existing_results = json.load(f)
        except json.JSONDecodeError:
            existing_results = []
    
    if not isinstance(existing_results, list):
        existing_results = []
    
    existing_results.append(json_results)
    
    # Apply history size limit if configured
    max_history = config.getoption("oof_max_history")
    if max_history > 0 and len(existing_results) > max_history:
        # Keep only the most recent runs up to max_history
        existing_results = existing_results[-max_history:]
    
    # Save JSON history
    with open(json_history_file, "w") as f:
        json.dump(existing_results, f, indent=2)

    # Update test history
    try:
        history = TestHistory.load(HISTORY_FILE)
    except (FileNotFoundError, EOFError, pickle.UnpicklingError):
        history = TestHistory()

    history.add_run(results)
    
    # Apply same limit to TestHistory
    if max_history > 0:
        history.limit_runs(max_history)
    
    history.save(HISTORY_FILE)
