"""CLI entry point for pytest-oof."""
import click
from rich.console import Console

from pytest_oof.cli.analyze import analyze
from pytest_oof.cli.examples import examples
from pytest_oof.cli.export import export

console = Console()

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "show_default": True,
    "max_content_width": 100,
}


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """pytest-oof: Pytest Outcomes and Output-Fields

    For example commands and usage:
        oof examples show

    To save examples to a file:
        oof examples show --save examples.md
    """
    pass


cli.add_command(analyze)
cli.add_command(export)
cli.add_command(examples)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
