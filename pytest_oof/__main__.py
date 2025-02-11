"""CLI entry point for pytest-oof."""
import click
from rich.console import Console

from pytest_oof.cli.analyze import analyze
from pytest_oof.cli.export import export
from pytest_oof.cli.examples import examples
from pytest_oof.cli.test_mode import test_mode
from pytest_oof.cli.generate import generate
from pytest_oof.cli.info import info

console = Console()

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "show_default": True,
    "max_content_width": 100,
}


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """pytest-oof: Pytest Outcomes and Output-Fields"""
    pass

cli.add_command(analyze)
cli.add_command(export)
cli.add_command(examples)
cli.add_command(test_mode)
cli.add_command(generate)
cli.add_command(info)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
