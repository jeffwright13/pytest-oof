import pytest

@pytest.mark.xfail(reason="This test is expected to fail")
def test_expected_failure():
    assert False, "This test is expected to fail"
