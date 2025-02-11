"""Constants used throughout pytest-oof."""
import os
from pathlib import Path

from pytest_oof.test_mode import get_test_mode

# Database paths
DEFAULT_DB_PATH = Path("./.oof/oof-results.db")
TEST_DB_PATH = Path("./.oof/oof-test-data.db")

# Ensure directories exist
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def get_active_db() -> Path:
    """Get the active database path based on test mode."""
    # Command line --db-path takes precedence over everything
    if "OOF_CLI_DB_PATH" in os.environ:
        return Path(os.environ["OOF_CLI_DB_PATH"])

    # Then check test mode
    return TEST_DB_PATH if get_test_mode() else DEFAULT_DB_PATH
