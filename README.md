# pytest-oof: pytest Outcomes and Output-Fields

## A pytest plugin providing structured access to post-run pytest results

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

## Target audience:
- Pytest plugin developers and others who need access to pytest's results after a test run has completed
- Testers who want a summary of their test run *as reported by pytest on the console* (doesn't get more authoritative than that), without having to parse pytest's complex console output
- Taylor Swift fans

## Installation

### Standard install
`pip install -i https://test.pypi.org/simple/ pytest-oof`

### For local development
- Clone the repo
- Make a venv; required dependencies are:
  - pytest (*duh*)
  - rich
  - strip-ansi
  - single-source
  - pytest-rerunfailures (if you want to run the demo tests)
  - faker (if you want to run the demo tests)
- Install the plugin: `pip install .`
- Use as below:
    - Run the demo console script: `oofda` (specify `--help` for options)
    - In your own code, `from pytest-oof.utils import Results` and use as you wish
    - In your `conftest.py`, use the custom hook as you wish


## Usage


### Demo script

First, run your pytest campaign with the `--oof` option:

`$ pytest --oof`

This generates two files in the `/oof` directory:
- oof/results.pickle: a pickled collection of dataclasses representing all results in an easy-to-consume format
- oof/terminal_output.ansi: a copy of the entire terminal output from your test session, encoded in ANSI escape codes

Now run the included console script `oofda`:

`$ oofda`

This script invokes the example code in `__main__.py`, shows how to consume the oof files, and presents basic results on the console.

Go ahead - compare the results with the last line of output from `pytest --oof` .

### As an importable module

Run your pytest campaign with the `--oof` option:

`$ pytest --oof`

Now use as you wish:

```
from pytest_oof.utils import Results

results = Results.from_files(
    results_file_path="oof/results.pickle",
    output_file_path="oof/terminal_output.ansi",
)
```

### As a pytest plugin with custom hooks

The 'results' parameter will be filled by pytest when the hook is called.
You can then access the test session data within this block, and do whatever you want with it.

`plugin.py` or `conftest.py`:
```
@pytest.hookimpl
def pytest_oof_results(results):
    print(f"Received results: {results}")
```

#### Example output

Here's a quick test that has all of the outcomes and scenarios you might encounter during a typical run.

```
$ pytest --oof

=========================================== test session starts ===========================================
platform darwin -- Python 3.11.4, pytest-7.4.3, pluggy-1.3.0 -- /Users/jwr003/coding/pytest-oof/venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/jwr003/coding/pytest-oof
plugins: oof-0.2.0, anyio-4.0.0, rerunfailures-12.0, tally-1.3.1
collecting ...
collected 11 items

demo-tests/test_basic.py::test_basic_pass_1 PASSED                                                  [  9%]
demo-tests/test_basic.py::test_basic_pass_3_error_in_fixture ERROR                                  [ 18%]
demo-tests/test_basic.py::test_basic_fail_1 FAILED                                                  [ 27%]
demo-tests/test_basic.py::test_basic_skip PASSED                                                    [ 36%]
demo-tests/test_basic.py::test_basic_xfail XFAIL                                                    [ 45%]
demo-tests/test_basic.py::test_basic_xpass XPASS                                                    [ 54%]
demo-tests/test_basic.py::test_basic_warning_1 PASSED                                               [ 63%]
demo-tests/test_basic.py::test_basic_warning_2 PASSED                                               [ 72%]
demo-tests/test_basic.py::test_basic_rerun_pass RERUN                                               [ 81%]
demo-tests/test_basic.py::test_basic_rerun_pass RERUN                                               [ 81%]
demo-tests/test_basic.py::test_basic_rerun_pass PASSED                                              [ 81%]
demo-tests/test_basic.py::test_basic_rerun_fail RERUN                                               [ 90%]
demo-tests/test_basic.py::test_basic_rerun_fail RERUN                                               [ 90%]
demo-tests/test_basic.py::test_basic_rerun_fail FAILED                                              [ 90%]
demo-tests/test_basic.py::test_basic_skip_marker SKIPPED (Skip this test with marker.)              [100%]

================================================= ERRORS ==================================================
__________________________ ERROR at setup of test_basic_pass_3_error_in_fixture ___________________________

fake_data = 'Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui ...odo id ut enim. Morbi ornare, nisi vel consectetur bibendum, nibh elit mollis quam, ac vestibulum velit est at turpis.'

    @pytest.fixture
    def error_fixt(fake_data):
>       raise Exception("Error in fixture")
E       Exception: Error in fixture

demo-tests/test_basic.py:27: Exception
================================================ FAILURES =================================================
____________________________________________ test_basic_fail_1 ____________________________________________

fake_data = 'Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commo... metus feugiat, gravida mi ac, sagittis nisl. Mauris varius sapien sed turpis congue, ac ullamcorper tortor tincidunt.'

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
__________________________________________ test_basic_rerun_fail __________________________________________

    @pytest.mark.flaky(reruns=2)
    def test_basic_rerun_fail():
>       assert False
E       assert False

demo-tests/test_basic.py:144: AssertionError
============================================ warnings summary =============================================
demo-tests/test_basic.py::test_basic_warning_1
  /Users/jwr003/coding/pytest-oof/demo-tests/test_basic.py:112: UserWarning: api v1, should use functions from v2
    warnings.warn(UserWarning("api v1, should use functions from v2"))

demo-tests/test_basic.py::test_basic_warning_2
  /Users/jwr003/coding/pytest-oof/demo-tests/test_basic.py:117: UserWarning: api v2, should use functions from v3
    warnings.warn(UserWarning("api v2, should use functions from v3"))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================================= PASSES ==================================================
========================================= rerun test summary info =========================================
RERUN demo-tests/test_basic.py::test_basic_rerun_pass
RERUN demo-tests/test_basic.py::test_basic_rerun_pass
RERUN demo-tests/test_basic.py::test_basic_rerun_fail
RERUN demo-tests/test_basic.py::test_basic_rerun_fail
========================================= short test summary info =========================================
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
======= 2 failed, 5 passed, 1 skipped, 1 xfailed, 1 xpassed, 2 warnings, 1 error, 4 rerun in 0.23s ========
```

And here's the result of the included sample script that consumes pytest-oof's output files. As you can see, you have easy access to all the individual test results, as well as the various sections of the console output.

```
$ oofda

Session start time: 2023-11-05 16:42:48.540273
Session end time: 2023-11-05 16:42:48.804730
Session duration: 0:00:00.264457


Number of tests: 15
Number of passes: 5
Number of failures: 2
Number of errors: 1
Number of skips: 1
Number of xfails: 1
Number of xpasses: 1
Number of warnings: 2
Number or reruns: 4


Output field name: pre_test
Output field content:


Output field name: test_session_starts
Output field content:
[1m=========================================== test session starts
===========================================[0m
platform darwin -- Python 3.11.4, pytest-7.4.3, pluggy-1.3.0 --
/Users/jwr003/coding/pytest-oof/venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/jwr003/coding/pytest-oof
plugins: oof-0.2.0, anyio-4.0.0, rerunfailures-12.0, tally-1.3.1
[1mcollecting ...
[0m[1mcollected 11 items
[0m

demo-tests/test_basic.py::test_basic_pass_1 [32mPASSED[0m[32m
[  9%][0m
demo-tests/test_basic.py::test_basic_pass_3_error_in_fixture [31mERROR[0m[31m
[ 18%][0m
demo-tests/test_basic.py::test_basic_fail_1 [31mFAILED[0m[31m
[ 27%][0m
demo-tests/test_basic.py::test_basic_skip [32mPASSED[0m[31m
[ 36%][0m
demo-tests/test_basic.py::test_basic_xfail [33mXFAIL[0m[31m
[ 45%][0m
demo-tests/test_basic.py::test_basic_xpass [33mXPASS[0m[31m
[ 54%][0m
demo-tests/test_basic.py::test_basic_warning_1 [32mPASSED[0m[31m
[ 63%][0m
demo-tests/test_basic.py::test_basic_warning_2 [32mPASSED[0m[31m
[ 72%][0m
demo-tests/test_basic.py::test_basic_rerun_pass [33mRERUN[0m[31m
[ 81%][0m
demo-tests/test_basic.py::test_basic_rerun_pass [33mRERUN[0m[31m
[ 81%][0m
demo-tests/test_basic.py::test_basic_rerun_pass [32mPASSED[0m[31m
[ 81%][0m
demo-tests/test_basic.py::test_basic_rerun_fail [33mRERUN[0m[31m
[ 90%][0m
demo-tests/test_basic.py::test_basic_rerun_fail [33mRERUN[0m[31m
[ 90%][0m
demo-tests/test_basic.py::test_basic_rerun_fail [31mFAILED[0m[31m
[ 90%][0m
demo-tests/test_basic.py::test_basic_skip_marker [33mSKIPPED[0m (Skip this test with marker.)[31m
[100%][0m



Output field name: errors
Output field content:
================================================= ERRORS ==================================================
[31m[1m__________________________ ERROR at setup of test_basic_pass_3_error_in_fixture
___________________________[0m

fake_data = 'Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae
consequatur, vel illum qui ...odo id ut enim. Morbi ornare, nisi vel consectetur bibendum, nibh elit mollis
quam, ac vestibulum velit est at turpis.'

    [37m@pytest[39;49;00m.fixture[90m[39;49;00m
    [94mdef[39;49;00m [92merror_fixt[39;49;00m(fake_data):[90m[39;49;00m
>       [94mraise[39;49;00m [96mException[39;49;00m([33m"[39;49;00m[33mError in
fixture[39;49;00m[33m"[39;49;00m)[90m[39;49;00m
[1m[31mE       Exception: Error in fixture[0m

[1m[31mdemo-tests/test_basic.py[0m:27: Exception


Output field name: failures
Output field content:
================================================ FAILURES =================================================
[31m[1m____________________________________________ test_basic_fail_1
____________________________________________[0m

fake_data = 'Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi
ut aliquid ex ea commo... metus feugiat, gravida mi ac, sagittis nisl. Mauris varius sapien sed turpis
congue, ac ullamcorper tortor tincidunt.'

    [94mdef[39;49;00m [92mtest_basic_fail_1[39;49;00m(fake_data):[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
        logger.debug(fake_data)[90m[39;49;00m
>       [94massert[39;49;00m [94m1[39;49;00m == [94m2[39;49;00m[90m[39;49;00m
[1m[31mE       assert 1 == 2[0m

[1m[31mdemo-tests/test_basic.py[0m:57: AssertionError
[31m[1m__________________________________________ test_basic_rerun_fail
__________________________________________[0m

    [37m@pytest[39;49;00m.mark.flaky(reruns=[94m2[39;49;00m)[90m[39;49;00m
    [94mdef[39;49;00m [92mtest_basic_rerun_fail[39;49;00m():[90m[39;49;00m
>       [94massert[39;49;00m [94mFalse[39;49;00m[90m[39;49;00m
[1m[31mE       assert False[0m

[1m[31mdemo-tests/test_basic.py[0m:144: AssertionError


Output field name: passes
Output field content:
================================================= PASSES ==================================================


Output field name: warnings_summary
Output field content:
[33m============================================ warnings summary
=============================================[0m
demo-tests/test_basic.py::test_basic_warning_1
  /Users/jwr003/coding/pytest-oof/demo-tests/test_basic.py:112: UserWarning: api v1, should use functions
from v2
    warnings.warn(UserWarning("api v1, should use functions from v2"))

demo-tests/test_basic.py::test_basic_warning_2
  /Users/jwr003/coding/pytest-oof/demo-tests/test_basic.py:117: UserWarning: api v2, should use functions
from v3
    warnings.warn(UserWarning("api v2, should use functions from v3"))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html


Output field name: rerun_test_summary
Output field content:
========================================= rerun test summary info =========================================
RERUN demo-tests/test_basic.py::test_basic_rerun_pass
RERUN demo-tests/test_basic.py::test_basic_rerun_pass
RERUN demo-tests/test_basic.py::test_basic_rerun_fail
RERUN demo-tests/test_basic.py::test_basic_rerun_fail


Output field name: short_test_summary
Output field content:
[36m[1m========================================= short test summary info
=========================================[0m
[32mPASSED[0m demo-tests/test_basic.py::[1mtest_basic_pass_1[0m
[32mPASSED[0m demo-tests/test_basic.py::[1mtest_basic_skip[0m
[32mPASSED[0m demo-tests/test_basic.py::[1mtest_basic_warning_1[0m
[32mPASSED[0m demo-tests/test_basic.py::[1mtest_basic_warning_2[0m
[32mPASSED[0m demo-tests/test_basic.py::[1mtest_basic_rerun_pass[0m
[33mSKIPPED[0m [1] demo-tests/test_basic.py:147: Skip this test with marker.
[33mXFAIL[0m demo-tests/test_basic.py::[1mtest_basic_xfail[0m
[33mXPASS[0m demo-tests/test_basic.py::[1mtest_basic_xpass[0m
[31mERROR[0m demo-tests/test_basic.py::[1mtest_basic_pass_3_error_in_fixture[0m - Exception: Error in
fixture
[31mFAILED[0m demo-tests/test_basic.py::[1mtest_basic_fail_1[0m - assert 1 == 2
[31mFAILED[0m demo-tests/test_basic.py::[1mtest_basic_rerun_fail[0m - assert False


Output field name: lastline
Output field content:
[31m======= [31m[1m2 failed[0m, [32m5 passed[0m, [33m1 skipped[0m, [33m1 xfailed[0m, [33m1 xpassed[0m,
[33m2 warnings[0m, [31m[1m1 error[0m, [33m4 rerun[0m[31m in 0.23s[0m[31m ========[0m
```

## Limitations and Disclaimer

`pytest-oof` uses pytest's console output in order to generate its results. This means that if pytest changes its output format, `pytest-oof` may break. I will do my best to keep up with changes to pytest, but I make no guarantees. So far the same algorithm has held up for 2+ years, but who knows what the pytest devs will do next?

Because it is parsing the console output, it also means that you won't have access to the results until after the test run has completed (specifically, in `pytest_unconfigure`). Once the test run is over, you are left with two files, as discussed above. If you want to consume a test run's results in real-time, you'll need to use pytest's hooks, and/or other plugins (see below for a suggestion).

I developed the algorithm used in this plugin while writing [pytest-tui](https://github.com/jeffwright13/pytest-tui), because I couldn't find another way to correctly determine the outcome types for the more esoteric outcomes like XPass, XFail, or Rerun. I knew there is a way to determine some of this from analyzing succesive TestReport objects, but that still didn't do Reruns correctly, nor Warnings (which are technically not an outcome, but a field in the console output). This plugin gives you all that, plus a string of the individual fields/sections of the console output (like "warnings_summary," "errors," "failures," etc).

If you have any problems or questions with pytest-oof, open an issue. I'll do my best to address it.

## Other Ways to Get Tets Run Info ##

- pytest-json-encode


I do have code that outputs JSON-formatted results in real-time (part of [pytest-tally](https://github.com/jeffwright13/pytest-tally)). This code does *not* rely on the console output, intead getting its information from internal TestReport ojects as they are populated during a test run. In that respect, they are less fragile than pytest-oof. This method gets close to providing a complete representation of a test run's information, but does not include fields/sections, nor does it correectly handle all ways of skipping tests. However, that code is embedded in the tally library and is not prductized. I may do so and include it here in the future if there is any demand.
