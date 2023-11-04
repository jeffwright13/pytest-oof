# pytest-oof: Pytest Outcomes and Output-Fields

## A Pytest plugin providing structured access to your pytest results

### Test outcomes:
- Passes
- Failures
- Errors
- Skips
- Xfails
- XPasses
- Warnings
- Reruns

### Grouped reruns:
- Rerun tests listed individually
- Reruns listed by "rerun group" (i.e. all reruns of a given test, with final outcome assigned to group)

### Test output fields (aka "sections"):
- live_log_sessionstart
- test_session_starts
- errors
- failures
- passes
- warnings_summary
- rerun_test_summary
- short_test_summary
- lastline

## Installation

- Clone the repo
- Make a venv; required dependencies are:
  - pytest
  - rich
  - strip-ansi
  - single-source
  - pytest-rerunfailures (if you want to run the demo tests)
  - faker (if you want to run the demo tests)
- Install the plugin: `pip install .`


## Usage

First, run your pytest campaign with the `--oof` option:

`$ pytest --oof`

This generates two files in the `/oof` directory:
- oof/results.pickle: a pickled collection of dataclasses representing all results in an easy-to-consume format
- oof/termina_output.ansi: a copy of the entire terminal output from your test session, encoded in ANSI escape codes

Now run the included console script `oofda`:

`$ oofda`

This script invokes the example code in `__main__.py`, shows how to consume the oof files, and presents basic results on the console.

Go ahead - compare the results with the last line of output from `pytest --oof` .


## Example output

Here's a quick test that has all of the outcomes and scenarios you might encounter during a typical run.

```
$  pytest --oof
================================================ test session starts ================================================
platform darwin -- Python 3.11.4, pytest-7.4.3, pluggy-1.3.0 -- /Users/jwr003/coding/pytest-oof/venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/jwr003/coding/pytest-oof
plugins: anyio-4.0.0, rerunfailures-12.0, oof-0.1.0
collecting ...
collected 11 items

demo-tests/test_basic.py::test_basic_pass_1 PASSED                                                            [  9%]
demo-tests/test_basic.py::test_basic_pass_3_error_in_fixture ERROR                                            [ 18%]
demo-tests/test_basic.py::test_basic_fail_1 FAILED                                                            [ 27%]
demo-tests/test_basic.py::test_basic_skip PASSED                                                              [ 36%]
demo-tests/test_basic.py::test_basic_xfail XFAIL                                                              [ 45%]
demo-tests/test_basic.py::test_basic_xpass XPASS                                                              [ 54%]
demo-tests/test_basic.py::test_basic_warning_1 PASSED                                                         [ 63%]
demo-tests/test_basic.py::test_basic_warning_2 PASSED                                                         [ 72%]
demo-tests/test_basic.py::test_basic_rerun_pass RERUN                                                         [ 81%]
demo-tests/test_basic.py::test_basic_rerun_pass RERUN                                                         [ 81%]
demo-tests/test_basic.py::test_basic_rerun_pass PASSED                                                        [ 81%]
demo-tests/test_basic.py::test_basic_rerun_fail RERUN                                                         [ 90%]
demo-tests/test_basic.py::test_basic_rerun_fail RERUN                                                         [ 90%]
demo-tests/test_basic.py::test_basic_rerun_fail FAILED                                                        [ 90%]
demo-tests/test_basic.py::test_basic_skip_marker SKIPPED (Skip this test with marker.)                        [100%]

====================================================== ERRORS =======================================================
_______________________________ ERROR at setup of test_basic_pass_3_error_in_fixture ________________________________

fake_data = 'Praesent commodo commodo est, at maximus metus bibendum vitae. Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium. Lorem ipsum dolor sit amet, consectetur adipiscing elit.'

    @pytest.fixture
    def error_fixt(fake_data):
>       raise Exception("Error in fixture")
E       Exception: Error in fixture

demo-tests/test_basic.py:27: Exception
===================================================== FAILURES ======================================================
_________________________________________________ test_basic_fail_1 _________________________________________________

fake_data = 'Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudianda...risus suscipit. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.'

    def test_basic_fail_1(fake_data):
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
        logger.debug(fake_data)
>       assert 1 == 2
E       assert 1 == 2

demo-tests/test_basic.py:57: AssertionError
_______________________________________________ test_basic_rerun_fail _______________________________________________

    @pytest.mark.flaky(reruns=2)
    def test_basic_rerun_fail():
>       assert False
E       assert False

demo-tests/test_basic.py:144: AssertionError
================================================= warnings summary ==================================================
demo-tests/test_basic.py::test_basic_warning_1
  /Users/jwr003/coding/pytest-oof/demo-tests/test_basic.py:112: UserWarning: api v1, should use functions from v2
    warnings.warn(UserWarning("api v1, should use functions from v2"))

demo-tests/test_basic.py::test_basic_warning_2
  /Users/jwr003/coding/pytest-oof/demo-tests/test_basic.py:117: UserWarning: api v2, should use functions from v3
    warnings.warn(UserWarning("api v2, should use functions from v3"))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================================================== PASSES =======================================================
============================================== rerun test summary info ==============================================
RERUN demo-tests/test_basic.py::test_basic_rerun_pass
RERUN demo-tests/test_basic.py::test_basic_rerun_pass
RERUN demo-tests/test_basic.py::test_basic_rerun_fail
RERUN demo-tests/test_basic.py::test_basic_rerun_fail
============================================== short test summary info ==============================================
PASSED demo-tests/test_basic.py::test_basic_pass_1
PASSED demo-tests/test_basic.py::test_basic_skip
PASSED demo-tests/test_basic.py::test_basic_warning_1
PASSED demo-tests/test_basic.py::test_basic_warning_2
PASSED demo-tests/test_basic.py::test_basic_rerun_pass
SKIPPED [1] demo-tests/test_basic.py:147: Skip this test with marker.
XFAIL demo-tests/test_basic.py::test_basic_xfail
XPASS demo-tests/test_basic.py::test_basic_xpass
ERROR demo-tests/test_basic.py::test_basic_pass_3_error_in_fixture - Exception: Error in fixture
FAILED demo-tests/test_basic.py::test_basic_fail_1 - assert 1 == 2
FAILED demo-tests/test_basic.py::test_basic_rerun_fail - assert False
============ 2 failed, 5 passed, 1 skipped, 1 xfailed, 1 xpassed, 2 warnings, 1 error, 4 rerun in 0.23s =============
```

And here's the result of the included sample script that consumes pytest-oof's output files:

```
$ oofda

Session start time: 2023-11-04 06:27:34.495529
Session end time: 2023-11-04 06:27:34.741546
Session duration: 0:00:00.246017
Number of tests: 15
Number of passes: 5
Number of failures: 2
Number of errors: 1
Number of skips: 1
Number of xfails: 1
Number of xpasses: 1
Number of warnings: 2
Number or reruns: 4
```

## Disclaimer

`pytest-oof` uses the console output in order to generate its results.  This means that it is dependent on the output format of pytest, and that if pytest changes its output format, `pytest-oof` may break.  I will do my best to keep up with changes to pytest, but I make no guarantees. So far the same algorithm has held up for 2+ years, but who knows that the pytest devs will do next?

I developed the algorithm used in this plugin because I couldn't find another way to correctly determine the outcome types for the more esoteric outcomes like XPass, XFail, or Rerun. I know there is a way to determine some of this from analyzing succesive TestReport objects, but that still didn't do Reruns correctly, nor Warnings (which are technically not an outcome, but a field in the console object). Tihs plugin gives you all that, plus a string of the individual fields/sections of the console output (like "warnings_summary," "errors," "failures," etc).

If you have any issues, please open an issue on the repo.  I'll do my best to address it.
