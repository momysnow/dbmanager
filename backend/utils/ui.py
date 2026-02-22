import os
import shutil
from typing import Any, List, Optional, cast

from rich.console import Console
from InquirerPy import inquirer

# Fix for Docker environments where terminal size might be (0, 0)
# Set environment variables as fallback
os.environ.setdefault("COLUMNS", "120")
os.environ.setdefault("LINES", "40")

# Patch shutil.get_terminal_size to ensure it never returns 0
_original_get_terminal_size = shutil.get_terminal_size


def _patched_get_terminal_size(
    fallback: tuple[int, int] = (120, 40)
) -> os.terminal_size:
    try:
        size = _original_get_terminal_size(fallback)
        # Ensure width and height are never 0
        return os.terminal_size((max(size.columns, 80), max(size.lines, 24)))
    except Exception:
        return os.terminal_size(fallback)


shutil.get_terminal_size = _patched_get_terminal_size

console = Console()


def print_header() -> None:
    console.clear()
    console.print("[bold cyan]DB Manager CLI[/bold cyan]", justify="center")
    console.print("Manage your databases with ease", justify="center", style="italic")
    console.print("-" * 50, justify="center")
    console.print("\n")


def get_input(prompt_text: str, default: Optional[str] = None) -> str:
    return cast(
        str, inquirer.text(message=prompt_text, default=default or "").execute()
    )


def get_confirm(prompt_text: str, default: bool = True) -> bool:
    return cast(bool, inquirer.confirm(message=prompt_text, default=default).execute())


def get_selection(message: str, choices: List[Any], default: Any = None) -> Any:
    return inquirer.select(
        message=message, choices=choices, default=default, pointer=">"
    ).execute()


def print_success(message: str) -> None:
    console.print(f"[bold green]SUCCESS:[/bold green] {message}")


def print_error(message: str) -> None:
    console.print(f"[bold red]ERROR:[/bold red] {message}")


def print_info(message: str) -> None:
    console.print(f"[blue]{message}[/blue]")
