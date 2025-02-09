"""CLI entry point for pytest-oof."""
import os
import subprocess

import click
from rich.console import Console

from pytest_oof.cli.analyze import analyze
from pytest_oof.cli.export import export
from pytest_oof.cli.examples import examples

console = Console()

@click.group()
def cli():
    """pytest-oof: Test Results Analysis Tool
    
    For example commands and usage:
        oof examples show
        
    To save examples to a file:
        oof examples show --save examples.md
    """
    pass

cli.add_command(analyze)
cli.add_command(export)
cli.add_command(examples)

@cli.group()
def view():
    """View test results."""
    pass

@view.command()
def tui():
    """View results in terminal UI."""
    console.print("Launching TUI...", style="green")
    subprocess.run(["oof-tui"])

@view.command()
def console():
    """View results in console."""
    console.print("Executing Simple UI...", style="green")
    subprocess.run(["oof-console"])

def main():
    cli()

if __name__ == "__main__":
    main()
