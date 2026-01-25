from rich.console import Console
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

console = Console()

def print_header():
    console.clear()
    console.print("[bold cyan]DB Manager CLI[/bold cyan]", justify="center")
    console.print("Manage your databases with ease", justify="center", style="italic")
    console.print("-" * 50, justify="center")
    console.print("\n")

def get_input(prompt_text: str, default: str = None) -> str:
    return inquirer.text(message=prompt_text, default=default or "").execute()

def get_confirm(prompt_text: str, default: bool = True) -> bool:
    return inquirer.confirm(message=prompt_text, default=default).execute()

def get_selection(message: str, choices: list, default: any = None):
    return inquirer.select(
        message=message,
        choices=choices,
        default=default,
        pointer=">"
    ).execute()

def print_success(message: str):
    console.print(f"[bold green]SUCCESS:[/bold green] {message}")

def print_error(message: str):
    console.print(f"[bold red]ERROR:[/bold red] {message}")

def print_info(message: str):
    console.print(f"[blue]{message}[/blue]")
