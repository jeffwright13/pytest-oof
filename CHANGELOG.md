# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project tries to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## UNRELEASED
- N/A

## [1.1.0] 2023-12-10
- Fixed issue 1 (individual test reports are missing section separators)
- Implemented centralized logging with UTC timestamps in conftest.py for demo-tests.

## [1.0.1] 2023-12-04
- Added "-s | --summary" option to 'oofda' script

## [1.0.0] 2023-11-12
- Improved 'oofda' script to break down Reruns into Total Num Reruns vs. Total Num Unique Reruns
- Removed unused "live_log_sessionstart" output field; any live log section data is
  included in the relevant capture section

## [0.3.2] 2023-11-08
- Changed internal use of term "fqtn" to pytest-standard "nodeid"
- Updated README.md to include class definitions

## [0.3.1] 2023-11-07
- Support for standard install with `pip`

## [0.3.0] 2023-11-05
- Added 'has_warning' attribute to TestResult object
- Removed dependency on terminal_out.ansi

## [0.2.0] 2023-11-05
- Improved console script (allows specifying file location; improved search mechanism))
- Added hook "pytest_oof_results"

## [0.1.1] 2023-11-03
- Fixed console script (there was a conflicting name)

## [0.1.0] 2023-11-03
- Working code, including warnings count

## [0.0.1] 2023-11-03
- Initial code, adapted from `pytest-tui`
