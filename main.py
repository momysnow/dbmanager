"""DBManager CLI - Entry Point"""
import typer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager
from cli.database import manage_databases_menu, add_database_wizard
from cli.s3 import manage_s3_buckets_menu
from cli.schedule import schedule_menu
from cli.settings import settings_menu
from utils.ui import print_header, get_selection

app = typer.Typer()

# ═══════════════════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@app.command()
def perform_backup(db_id: int = typer.Option(..., help="ID of the database to backup")):
    """Internal command used by cron to perform scheduled backups."""
    try:
        path = manager.backup_database(db_id)
        print(f"Backup successful: {path}") 
    except Exception as e:
        print(f"Backup failed: {e}")
        raise typer.Exit(code=1)

@app.command()
def interactive():
    """Starts the interactive shell mode."""
    while True:
        print_header()
        choices = [
            Choice(value="manage", name="Manage Databases"),
            Choice(value="add", name="Add Database"),
            Choice(value="schedule", name="Schedule Backups"),
            Choice(value="s3", name="Manage S3 Buckets"),
            Choice(value="settings", name="Settings"),
            Separator(),
            Choice(value="exit", name="Exit"),
        ]
        
        action = get_selection("Main Menu", choices)
        
        if action == "manage":
            manage_databases_menu()
        elif action == "add":
            add_database_wizard()
        elif action == "schedule":
            schedule_menu()
        elif action == "s3":
            manage_s3_buckets_menu()
        elif action == "settings":
            settings_menu()
        elif action == "exit":
            console.print("Goodbye!")
            break

# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()
