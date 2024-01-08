import pytest

from .utils import Results


class HookSpecs:
    @pytest.hookspec(firstresult=True)
    def pytest_oof_results(self, results: Results) -> Results:
        """
        Called after the test session is finished to provide a Results
        instance with the collected test session data.
        """
