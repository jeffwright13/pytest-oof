"""CLI commands for pytest-oof."""
import click
from rich.console import Console

from pytest_oof.cli.analyze import analyze
from pytest_oof.cli.examples import examples
from pytest_oof.cli.export import export
from pytest_oof.cli.generate import generate
from pytest_oof.cli.info import info
from pytest_oof.cli.test_mode import test_mode
from pytest_oof.test_mode import print_test_mode_warning

console = Console()

@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True}
)
def cli():
    """CLI for pytest-oof."""
    # Print test mode warning before every command
    print_test_mode_warning()

# Add all command groups
cli.add_command(analyze)
cli.add_command(examples)
cli.add_command(export)
cli.add_command(generate)
cli.add_command(info)
cli.add_command(test_mode)
