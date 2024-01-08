import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

from rich import print

from pytest_oof.utils import RESULTS_FILE, Results


def search_for_oof_files() -> Dict[str, Path]:
    """Search for the results files in the current working directory."""
    d = {
        "results": path
        for path in Path.cwd().iterdir()
        if path.is_file() and path.name == RESULTS_FILE.name
    }
    return d


def parse_args() -> str:
    parser = argparse.ArgumentParser(
        description="Process output from pytest-oof test run, and display Results and TerminalOutput in console."
    )
    parser.add_argument(
        "-r",
        "--results-file",
        type=str,
        help="Path to the results file (results.pickle)",
    )
    parser.add_argument(
        "-t",
        "--terminal-output-file",
        type=str,
        help="Path to the terminal output file (terminal_output.ansi)",
    )
    parser.add_argument(
        "-s",
        "--summary",
        action="store_true",
        help="Print test results summary only (no output fields)",
    )

    return parser.parse_args()


def main() -> None:
    # Get the file from command line arguments or defaults
    # args, results_file = parse_args_and_get_files()
    args = parse_args()

    # Usage example:
    try:
        results = Results.from_file(RESULTS_FILE)
    except (FileNotFoundError, UnboundLocalError) as e:
        msg = f"{str(e)}.\nNo results file found. Try specifying the file with the -r flag, or running this script from the default install directory."
        raise type(e)(msg).with_traceback(e.__traceback__)

    # Access the test run data using dot notation or built-in methods (bragable):
    print(
        f"\nSession start time: {datetime.strftime(results.session_start_time, '%Y-%m-%d %H:%M:%S.%f')}"
    )
    print(
        f"Session end time: {datetime.strftime(results.session_stop_time, '%Y-%m-%d %H:%M:%S.%f')}"
    )
    print(
        f"Session duration: {timedelta(seconds=results.session_duration.total_seconds())}"
    )

    print(f"\nNumber of tests: {len(results.test_results.all_tests())}")
    print(f"Number of passes: {len(results.test_results.all_passes())}")
    print(f"Number of failures: {len(results.test_results.all_failures())}")
    print(f"Number of errors: {len(results.test_results.all_errors())}")
    print(f"Number of skips: {len(results.test_results.all_skips())}")
    print(f"Number of xfails: {len(results.test_results.all_xfails())}")
    print(f"Number of xpasses: {len(results.test_results.all_xpasses())}")
    print(f"Number of reruns (total): {len(results.test_results.all_reruns())}")
    print(
        f"Number of reruns (unique): {len(set([rerun.nodeid for rerun in results.test_results.all_reruns()]))}"
    )
    print(f"Number of tests with warnings: {len(results.test_results.all_warnings())}")

    if not args.summary:
        print(f"\nOutput field name: {results.output_fields.test_session_starts.name}")
        print(
            f"Output field content: \n{results.output_fields.test_session_starts.content}"
        )
        print(f"\nOutput field name: {results.output_fields.errors.name}")
        print(f"Output field content: \n{results.output_fields.errors.content}")
        print(f"\nOutput field name: {results.output_fields.failures.name}")
        print(f"Output field content: \n{results.output_fields.failures.content}")
        print(f"\nOutput field name: {results.output_fields.passes.name}")
        print(f"Output field content: \n{results.output_fields.passes.content}")
        print(f"\nOutput field name: {results.output_fields.warnings_summary.name}")
        print(
            f"Output field content: \n{results.output_fields.warnings_summary.content}"
        )
        print(f"\nOutput field name: {results.output_fields.rerun_test_summary.name}")
        print(
            f"Output field content: \n{results.output_fields.rerun_test_summary.content}"
        )
        print(f"\nOutput field name: {results.output_fields.short_test_summary.name}")
        print(
            f"Output field content: \n{results.output_fields.short_test_summary.content}"
        )
        print(f"\nOutput field name: {results.output_fields.lastline.name}")
        print(f"Output field content: \n{results.output_fields.lastline.content}")


if __name__ == "__main__":
    main()
