import itertools
import json
import pickle
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
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
    JSON_OUT_FILE,
    RESULTS_FILE,
    TERMINAL_OUTPUT_FILE,
    generate_timestamp_uuid,
    OutputField,
    OutputFields,
    RerunTestGroup,
    Results,
    TestResult,
    TestResults,
    SessionMetadata,
    TestSessionStats,
    TestHistory,
    HISTORY_FILE,
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
    @classmethod
    def from_config(
        cls, config: Config
    ):  # 'config' refers to global pytest Config object
        # Create SessionMetadata with SUT information
        session_metadata = SessionMetadata(
            session_id=config._oof_session_id,
            start_time=config._oof_session_start_time,
            stop_time=config._oof_session_stop_time,
            duration=config._oof_session_duration,
        )
        
        return cls(
            session_id=config._oof_session_id,
            session_stats=config._oof_session_stats,
            session_start_time=config._oof_session_start_time,
            session_stop_time=config._oof_session_stop_time,
            session_duration=config._oof_session_duration,
            test_results=config._oof_test_results.test_results,
            output_fields=config._oof_fields,
            warnings=config._oof_test_results.all_warnings(),
            rerun_test_groups=config._oof_rerun_test_groups,
        )


def pytest_addoption(parser: Parser) -> None:
    group = parser.getgroup("oof")
    group.addoption(
        "--oof",
        action="store_true",
        dest="_oof",
        default=None,
        help=("Enable the pytest-oof plugin."),
    )
    group.addoption(
        "--sut-id",
        action="store",
        dest="_sut_id",
        default="",
        help="Unique identifier for the system under test",
    )
    group.addoption(
        "--sut-type",
        action="store",
        dest="_sut_type",
        default="",
        help="Type/category of the system (e.g., 'GEMS', 'production', 'staging')",
    )
    group.addoption(
        "--sut-version",
        action="store",
        dest="_sut_version",
        default="",
        help="Version information about the system under test",
    )
    group.addoption(
        "--sut-env",
        action="store",
        dest="_sut_environment",
        default="",
        help="Environment details (e.g., 'prod', 'staging', 'dev')",
    )
    group.addoption(
        "--sut-metadata",
        action="store",
        dest="_sut_metadata",
        default="{}",
        help="JSON string containing additional SUT-specific metadata",
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
            "start_time": None,   # Will be set when the session starts
            "stop_time": None,    # Will be set when the session ends
            "duration": None      # Will be calculated later
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
    sut_id = config.getoption("_sut_id")
    sut_type = config.getoption("_sut_type")
    sut_version = config.getoption("_sut_version")
    sut_environment = config.getoption("_sut_environment")
    try:
        sut_metadata = json.loads(config.getoption("_sut_metadata"))
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
    rerun_summary = config._oof_fields.rerun_test_summary.content
    rerun_nodeids = set()
    for line in rerun_summary.split('\n'):
        if line.startswith('RERUN '):
            nodeid = line.replace('RERUN ', '').strip()
            rerun_nodeids.add(nodeid)

    # Update num_rerun_groups with the number of unique nodeids from summary
    config._oof_session_stats.num_rerun_groups = len(rerun_nodeids)

    # For each nodeid that had reruns, create a RerunTestGroup object
    for nodeid, rerun_tests in rerun_tests_by_nodeid.items():
        # Find the final test result for this nodeid
        final_test = None
        for test_result in config._oof_test_results.test_results:
            if test_result.nodeid == nodeid and test_result.outcome != "RERUN":
                final_test = test_result
                break

        if final_test:
            rerun_test_group = RerunTestGroup(
                nodeid=nodeid,
                final_outcome=final_test.outcome,
                final_test=final_test,
                forerunners=rerun_tests,
            )
            rerun_test_group.full_test_list = rerun_tests + [final_test]
            rerun_test_groups.append(rerun_test_group)

    return rerun_test_groups


def mark_warning_tests(config: Config) -> List[TestResult]:
    """Mark tests that have warnings in the warnings field."""
    warning_tests = []
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
    with open(JSON_OUT_FILE, "w") as f:
        json.dump(results.to_dict(), f, indent=2)

    # Update test history
    try:
        history = TestHistory.load(HISTORY_FILE)
    except (FileNotFoundError, EOFError, pickle.UnpicklingError):
        history = TestHistory()

    history.add_run(results)
    history.save(HISTORY_FILE)
