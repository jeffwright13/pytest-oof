import os
import subprocess

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def html():
    console.print("Generating HTML from /oof...", style="green")
    subprocess.run(["oof-html"])
    html_file = os.path.join("/oof", "oof-html.html")
    subprocess.run(["python", "-m", "webbrowser", "-t", html_file])


@app.command()
def tui():
    console.print("Launching TUI...", style="green")
    subprocess.run(["oof-tui"])


@app.command()
def simple():
    console.print("Executing Simple UI...", style="green")
    subprocess.run(["oof-console"])


def main():
    app()


if __name__ == "__main__":
    main()
