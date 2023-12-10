import itertools
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
    RESULTS_FILE,
    TERMINAL_OUTPUT_FILE,
    OutputField,
    OutputFields,
    RerunTestGroup,
    Results,
    TestResult,
    TestResults,
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
warnings_summary_test_matcher = re.compile(r"^([^\n]+:{1,2}[^\n]+)\n([^\n]+\n)+")
lastline_matcher = re.compile(r"^==.*in\s\d+.\d+s.*=+")
standard_test_matcher = re.compile(
    r"(.*\::\S+)\s(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS|RERUN)"
)


@dataclass
class ResultsFromConfig(Results):
    @classmethod
    def from_config(cls, config: Config):
        return cls(
            session_start_time=config._oof_session_start_time,
            session_stop_time=config._oof_session_stop_time,
            session_duration=config._oof_session_duration,
            test_results=config._oof_test_results,
            rerun_test_groups=config._oof_rerun_test_groups,
            output_fields=config._oof_fields,
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
    # TODO: port to Stash in future; but this breaks backwards compatibility
    # for pytest < 7.0.
    config._oof_session_start_time = datetime.now(timezone.utc)
    if not hasattr(config, "_oof_sessionstart"):
        config._oof_sessionstart = True
    if not hasattr(config, "_oof_sessionstart_test_outcome_next"):
        config._oof_sessionstart_test_outcome_next = False
    if not hasattr(config, "_oof_sessionstart_current_nodeid"):
        config._oof_sessionstart_current_nodeid = ""
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
    config._oof_reports.append(report)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: Config) -> None:
    if not hasattr(config.option, "_oof"):
        return
    if not config.option._oof:
        return

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
            # field, populate the TestResult's fully qualified test name field.
            if config._oof_current_field == "test_session_starts":
                if config._oof_sessionstart_test_outcome_next:
                    outcome = s.strip()
                    config._oof_test_results.test_results[-1].outcome = outcome
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
            # populate the TestResult's outcome and the has_warning attribute.
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
            if isinstance(s_orig, str):
                unmarked_up = s_orig.encode("utf-8")
            config._oof_terminal_out.write(unmarked_up)

        # Write to both terminal/console and tempfiles
        tr._tw.write = tee_write


def populate_rerun_groups(config: Config) -> List[RerunTestGroup]:
    """Build a list of RerunTestGroup objects from the test results."""
    rerun_test_groups = []
    for test_result in config._oof_test_results.test_results:
        if test_result.outcome == "RERUN":
            if test_result.nodeid not in [group.nodeid for group in rerun_test_groups]:
                oof_test_run_group = RerunTestGroup(
                    nodeid=test_result.nodeid, forerunners=[test_result]
                )
                rerun_test_groups.append(oof_test_run_group)
            else:
                for group in rerun_test_groups:
                    if group.nodeid == test_result.nodeid:
                        group.forerunners.append(test_result)
    for test_result in config._oof_test_results.test_results:
        if test_result.outcome != "RERUN":
            for group in rerun_test_groups:
                if group.nodeid == test_result.nodeid:
                    group.test_outcome = test_result.outcome
                    group.final_test = test_result
    for group in rerun_test_groups:
        group.full_test_list = group.forerunners + [group.final_test]
    return rerun_test_groups


def pytest_unconfigure(config: Config) -> None:
    if not hasattr(config.option, "_oof"):
        return
    if not config.option._oof:
        return

    config._oof_rerun_test_groups = populate_rerun_groups(config)
    config._oof_session_stop_time = datetime.now(timezone.utc)
    config._oof_session_duration = (
        config._oof_session_stop_time - config._oof_session_start_time
    )

    # Populate test result objects with total durations, from each test's TestReport object.
    for oof_test_result, test_report in itertools.product(
        config._oof_test_results.test_results, config._oof_reports
    ):
        if test_report.nodeid == oof_test_result.nodeid:
            oof_test_result.duration += test_report.duration

    # Assume any test that was not categorized earlier with an outcome is a Skipped test.
    # JUSTIFICATION:
    # Pytest displays Skipped tests in a different format than all other test categories in the
    # "== short test summary info ==" field, truncating their nodeids and appending a line number
    # instead of specifying their test names. This plugin identifies all other test categories
    # (passed, failed, errors, etc.) and populates their nodeids and outcomes with the appropriate
    # values, leaving open one other possibility (Skipped).
    for oof_test_result in config._oof_test_results.test_results:
        if oof_test_result.outcome == "":
            oof_test_result.outcome = "SKIPPED"

    # Tag any test that has a warning with the has_warning attribute.
    nodeids = {result.nodeid for result in config._oof_test_results.test_results}
    warning_field = strip_ansi(config._oof_fields.warnings_summary.content)
    warning_lines = [
        line
        for line in warning_field.split("\n")
        if any(nodeid in line for nodeid in nodeids)
    ]
    warning_nodeids = {line.split()[0] for line in warning_lines}
    for test_result in config._oof_test_results.test_results:
        if test_result.nodeid in warning_nodeids:
            test_result.has_warning = True

    config.pluginmanager.getplugin(
        "terminalreporter"
    )  # <= ???  does not appear to be used

    # Rewind the temp file containing all the raw ANSI lines sent to the terminal;
    # read its contents;  then close it. Then, write info to file.
    config._oof_terminal_out.seek(0)
    terminal_out = config._oof_terminal_out.read()
    config._oof_terminal_out.close()
    with open(TERMINAL_OUTPUT_FILE, "wb") as file:
        file.write(terminal_out)

    # Write the test results to pickle file so we can access them as Python objects later.
    with open(RESULTS_FILE, "wb") as file:
        pickle.dump(
            {
                "oof_session_start_time": config._oof_session_start_time,
                "oof_session_stop_time": config._oof_session_stop_time,
                "oof_session_duration": config._oof_session_duration,
                "oof_test_results": config._oof_test_results,
                "oof_rerun_test_groups": config._oof_rerun_test_groups,
                "oof_fields": config._oof_fields,
            },
            file,
        )

    results = ResultsFromConfig.from_config(config)
    config.hook.pytest_oof_results(results=results, _pytest=True)
