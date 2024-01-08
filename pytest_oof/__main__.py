import os
import subprocess

import typer
from rich.console import Console as rich_console

from pytest_oof.utils import HTML_FILES_DIR

app = typer.Typer()
rich_console = rich_console()


@app.command()
def html():
    rich_console.print(f"Generating HTML in {HTML_FILES_DIR}/", style="green")
    subprocess.run(["oof-html"])
    html_file = os.path.join("/oof", "oof-html.html")
    subprocess.run(["python", "-m", "webbrowser", "-t", html_file])


@app.command()
def tui():
    rich_console.print("Launching TUI...", style="green")
    subprocess.run(["oof-tui"])


@app.command()
def console():
    rich_console.print("Executing Simple UI...", style="green")
    subprocess.run(["oof-console"])


def main():
    app()


if __name__ == "__main__":
    main()
