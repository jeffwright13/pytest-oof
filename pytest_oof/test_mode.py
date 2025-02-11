"""Test mode management for pytest-oof."""
import json
from pathlib import Path

from rich.console import Console

console = Console()

# Store test mode state in user's home directory to persist across sessions
TEST_MODE_FILE = Path.home() / ".oof" / "test_mode.json"
TEST_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)

def get_test_mode() -> bool:
    """Check if test mode is enabled."""
    if not TEST_MODE_FILE.exists():
        return False
    try:
        with TEST_MODE_FILE.open() as f:
            return json.load(f).get("enabled", False)
    except Exception:
        return False

def set_test_mode(enabled: bool) -> None:
    """Enable or disable test mode."""
    TEST_MODE_FILE.write_text(json.dumps({"enabled": enabled}))

def print_test_mode_warning():
    """Print a warning if test mode is enabled."""
    if get_test_mode():
        console.print(
            "\n[yellow on red]WARNING: TEST MODE ENABLED[/yellow on red]\n"
            "[yellow]All operations will use the test database.[/yellow]\n"
            "[dim]Run 'oof test-mode disable' to disable test mode.[/dim]\n"
        )
