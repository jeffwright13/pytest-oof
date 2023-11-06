import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from rich import print
from strip_ansi import strip_ansi

from pytest_oof.utils import RESULTS_FILE, TERMINAL_OUTPUT_FILE, OutputFields
from pytest_oof.utils import ResultsFromFiles as Results
from pytest_oof.utils import TestResult


def get_warning_fqtns(
    test_results: List[TestResult], output_fields: OutputFields
) -> List[str]:
    fqtns = [result.fqtn for result in test_results]
    warning_field = strip_ansi(output_fields.warnings_summary.content)
    warning_field_lines = [
        line
        for line in warning_field.split("\n")
        if any(fqtn in line for fqtn in fqtns)
    ]
    return [line.split()[0] for line in warning_field_lines]


def search_for_oof_files() -> Dict[str, Path]:
    """Search for the results files in the current working directory."""
    files = {}
    for path in Path.cwd().iterdir():
        if path.is_file():
            if path.name == RESULTS_FILE.name:
                files["results"] = path
            elif path.name == TERMINAL_OUTPUT_FILE.name:
                files["terminal_out"] = path
    return files


def parse_args_and_get_files() -> Tuple[Path, Path]:
    parser = argparse.ArgumentParser(description="Process some files.")
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

    args = parser.parse_args()

    if args.results_file:
        results_file = Path(args.results_file)
        print(f"Results file gotten from command line arguments: {results_file}")
    else:
        files = search_for_oof_files()
        # results_file = files.get("results", RESULTS_FILE)
        results_file = files.get("results")
        if results_file:
            print(f"Results file gotten from search: {results_file}")
        else:
            print(f"Results file gotten from default: {RESULTS_FILE}")
            results_file = RESULTS_FILE

    if args.terminal_output_file:
        terminal_output_file = Path(args.terminal_output_file)
        print(
            f"Terminal output file gotten from command line arguments: {terminal_output_file}"
        )
    else:
        files = search_for_oof_files()
        # terminal_output_file = files.get("terminal_out", TERMINAL_OUTPUT_FILE)
        terminal_output_file = files.get("terminal_out")
        if terminal_output_file:
            print(f"Terminal output file gotten from search: {terminal_output_file}")
        else:
            print(f"Terminal output file gotten from default: {TERMINAL_OUTPUT_FILE}")
            terminal_output_file = TERMINAL_OUTPUT_FILE

    return results_file, terminal_output_file


def main() -> None:
    # Get the files from command line arguments or defaults
    results_file, terminal_output_file = parse_args_and_get_files()

    # Usage example:
    try:
        results = Results.from_files(results_file, terminal_output_file)
    except (FileNotFoundError, UnboundLocalError) as e:
        msg = f"{str(e)}.\nNo results files found. Try specifying the files with the -r and -t flags, or running this script from the default install directory."
        raise type(e)(msg).with_traceback(e.__traceback__)

    # Access the test run data using dot notation or built-in methods (bragable):
    print(
        f"\nSession start time: {datetime.strftime(results.session_start_time, '%Y-%m-%d %H:%M:%S.%f')}"
    )
    print(
        f"Session end time: {datetime.strftime(results.session_end_time, '%Y-%m-%d %H:%M:%S.%f')}"
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
    print(
        f"Number of warnings: {len(get_warning_fqtns(results.test_results.test_results, results.output_fields))}"
    )
    print(f"Number or reruns: {len(results.test_results.all_reruns())}")

    print(f"\nOutput field name: {results.output_fields.live_log_sessionstart.name}")
    print(
        f"Output field content: \n{results.output_fields.live_log_sessionstart.content}"
    )
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
    print(f"Output field content: \n{results.output_fields.warnings_summary.content}")
    print(f"\nOutput field name: {results.output_fields.rerun_test_summary.name}")
    print(f"Output field content: \n{results.output_fields.rerun_test_summary.content}")
    print(f"\nOutput field name: {results.output_fields.short_test_summary.name}")
    print(f"Output field content: \n{results.output_fields.short_test_summary.content}")
    print(f"\nOutput field name: {results.output_fields.lastline.name}")
    print(f"Output field content: \n{results.output_fields.lastline.content}")


if __name__ == "__main__":
    main()
