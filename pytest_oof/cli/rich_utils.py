"""Rich utility functions for CLI output."""
from rich.console import Console
from rich.markdown import Markdown
from typing import Optional, Union, TextIO

console = Console(width=120)

def print_markdown(
    text: str, 
    code_theme: str = "monokai", 
    file: Optional[Union[TextIO, str]] = None
) -> None:
    """
    Print text as formatted Markdown using Rich.
    
    Args:
        text: Markdown-formatted text to print
        code_theme: Syntax highlighting theme for code blocks
        file: Optional file to write to instead of printing to console
    """
    markdown = Markdown(text, code_theme=code_theme)
    
    if file:
        # If file is a string, open it for writing
        if isinstance(file, str):
            with open(file, 'w') as f:
                console.print(markdown, file=f)
        else:
            # If file is a file-like object, write to it
            console.print(markdown, file=file)
    else:
        # Print to console
        console.print(markdown)

def format_command_help(description: str, examples: Optional[str] = None) -> str:
    """
    Format command help text with consistent Markdown styling.
    
    Args:
        description: Main description of the command
        examples: Optional examples section
    
    Returns:
        Formatted Markdown text
    """
    help_text = f"# Command Description\n\n{description}"
    
    if examples:
        help_text += f"\n\n# Examples\n\n{examples}"
    
    return help_text
