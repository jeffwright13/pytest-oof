import pytest

from .utils import Results

# def pytest_addhooks(pluginmanager: PytestPluginManager) -> None:
#     """Add hooks used by pytest-oof."""
#     print("Inside hooks.py/pytest_addhooks")
#     pluginmanager.add_hookspecs(HookSpecs)


class HookSpecs:
    @pytest.hookspec(firstresult=True)
    def pytest_oof_results(self, results: Results) -> Results:
        """
        Called after the test session is finished to provide a Results
        instance with the collected test session data.
        """
