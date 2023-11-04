from pytest_oof.utils import Results, TERMINAL_OUTPUT_FILE, RESULTS_FILE
from pathlib import Path
from datetime import datetime, timedelta

def main():
    # Usage example:
    results = Results.from_files(RESULTS_FILE, TERMINAL_OUTPUT_FILE)

    # Access the data using dot notation:
    print(f"Session start time: {datetime.strftime(results.session_start_time, '%Y-%m-%d %H:%M:%S.%f')}")
    print(f"Session end time: {datetime.strftime(results.session_end_time, '%Y-%m-%d %H:%M:%S.%f')}")
    print(f"Session duration: {timedelta(seconds=results.session_duration.total_seconds())}")

    print(f"Number of tests: {len(results.test_results.all_tests())}")
    print(f"Number of passes: {len(results.test_results.all_passes())}")
    print(f"Number of failures: {len(results.test_results.all_failures())}")
    print(f"Number of errors: {len(results.test_results.all_errors())}")
    print(f"Number of skips: {len(results.test_results.all_skips())}")
    print(f"Number of xfails: {len(results.test_results.all_xfails())}")
    print(f"Number of xpasses: {len(results.test_results.all_xpasses())}")
    print(f"Number or reruns: {len(results.test_results.all_reruns())}")



if __name__ == "__main__":
    main()
