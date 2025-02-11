"""CLI commands for managing test mode."""
import click
from rich.console import Console

from pytest_oof.test_mode import get_test_mode, set_test_mode

console = Console()

@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True}
)
def test_mode():
    """Manage test mode for oof commands."""
    pass

@test_mode.command()
def enable():
    """Enable test mode - use test database for all operations."""
    set_test_mode(True)
    console.print(
        "\n[green]Test mode enabled![/green]\n"
        "[yellow]All operations will now use the test database.[/yellow]\n"
        "[dim]Run 'oof test-mode disable' to disable test mode.[/dim]\n"
    )

@test_mode.command()
def disable():
    """Disable test mode - use production database for all operations."""
    set_test_mode(False)
    console.print(
        "\n[green]Test mode disabled![/green]\n"
        "All operations will now use the production database.\n"
    )

@test_mode.command()
def status():
    """Show current test mode status."""
    enabled = get_test_mode()
    if enabled:
        console.print(
            "\n[yellow on red]TEST MODE IS ENABLED[/yellow on red]\n"
            "[yellow]All operations are using the test database.[/yellow]\n"
            "[dim]Run 'oof test-mode disable' to disable test mode.[/dim]\n"
        )
    else:
        console.print(
            "\n[green]Test mode is disabled[/green]\n"
            "All operations are using the production database.\n"
        )
