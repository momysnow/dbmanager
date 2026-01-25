import typer
from rich.console import Console
from rich.table import Table
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from typing import Optional
from core.manager import DBManager
from core.cron import CronManager
from utils.ui import (
    print_header, get_input, print_success, print_error, 
    print_info, get_confirm, get_selection
)

app = typer.Typer()
console = Console()
manager = DBManager()
cron_manager = CronManager()

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
            Separator(),
            Choice(value="exit", name="Exit"),
        ]
        
        action = get_selection("Main Menu", choices)
        
        if action == "manage":
            manage_databases_menu()
        elif action == "add":
            add_database_wizard()
        elif action == "schedule":
            schedule_menu() # Changed from wizard to menu to allow listing
        elif action == "exit":
            console.print("Goodbye!")
            break

def schedule_menu():
    while True:
        choices = [
            Choice("add", "Schedule New Backup"),
            Choice("list", "List Scheduled Jobs"),
            Separator(),
            Choice("back", "Back")
        ]
        action = get_selection("Scheduling Menu", choices)
        
        if action == "back": break
        elif action == "add": schedule_wizard()
        elif action == "list": list_jobs_wizard()

def list_jobs_wizard():
    jobs = cron_manager.list_jobs()
    if not jobs:
        print_info("No active scheduled jobs.")
    else:
        table = Table(title="Scheduled Backups")
        table.add_column("DB ID", style="cyan")
        table.add_column("Schedule", style="magenta")
        table.add_column("Next Run", style="green") # Logic for next run? InquirerPy doesn't give it easily without Croniter.
        # Just show schedule string
        for job in jobs:
            table.add_row(job["id"], job["schedule"], "Enabled" if job["enabled"] else "Disabled")
        console.print(table)
    get_input("Press Enter...")

def manage_databases_menu():
    while True:
        dbs = manager.list_databases()
        if not dbs:
            print_info("No databases configured.")
            get_input("Press Enter to return...")
            return

        choices = []
        for db in dbs:
            name = f"{db['name']} ({db['provider']})"
            choices.append(Choice(value=db['id'], name=name))
        
        choices.append(Separator())
        choices.append(Choice(value="back", name="Back"))

        db_id = get_selection("Select a Database to Manage", choices)
        
        if db_id == "back":
            break
        
        # Sub-menu for specific DB
        db_actions_menu(int(db_id))

def db_actions_menu(db_id: int):
    while True:
        db = manager.config_manager.get_database(db_id)
        if not db:
            return

        print_header()
        console.print(f"Managing: [bold]{db['name']}[/bold] ({db['provider']})")
        
        choices = [
            Choice(value="check", name="Check Connection"),
            Choice(value="edit", name="Edit Configuration"),
            Choice(value="backup", name="Backup Now"),
            Choice(value="restore", name="Restore Backup"),
            Choice(value="delete", name="Delete Database"),
            Separator(),
            Choice(value="back", name="Back"),
        ]

        action = get_selection("Choose Action", choices)

        if action == "back":
            break
        elif action == "check":
            check_status(db_id)
        elif action == "edit":
            edit_database_wizard(db_id)
        elif action == "backup":
            perform_manual_backup(db_id)
        elif action == "restore":
            restore_wizard(db_id)
        elif action == "delete":
            if delete_database_wizard(db_id):
                break
        
        get_input("Press Enter to continue...")

def check_status(db_id: int):
    try:
        provider = manager.get_provider_instance(db_id)
        print_info(f"Checking {provider.name}...")
        if provider.check_connection():
            print_success("Online")
        else:
            print_error("Offline")
    except Exception as e:
        print_error(f"Error: {e}")

def perform_manual_backup(db_id: int):
    try:
        print_info("Starting backup...")
        path = manager.backup_database(db_id)
        print_success(f"Backup saved: {path}")
    except Exception as e:
        print_error(f"Backup failed: {e}")

def add_database_wizard():
    print_header()
    print_info("Add New Database")
    
    name = get_input("Display Name (alias):")
    if not name: return

    providers = manager.get_supported_providers()
    provider = get_selection("Select Provider", [Choice(p, p) for p in providers])
    
    host = get_input("Host:", "localhost")
    
    default_port = "5432"
    if provider == "mysql": default_port = "3306"
    elif provider == "sqlserver": default_port = "1433"
    
    port = get_input("Port:", default_port)
    user = get_input("Username:")
    password = get_input("Password (leave empty if none):")
    database = get_input("Database Name:")

    params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database
    }

    try:
        manager.add_database(name, provider, params)
        print_success("Database added!")
        get_input("Press Enter...")
    except Exception as e:
        print_error(f"Failed: {e}")
        get_input("Press Enter...")

def edit_database_wizard(db_id: int):
    db = manager.config_manager.get_database(db_id)
    if not db: return

    print_header()
    print_info(f"Editing Database: {db['name']}")

    # Pre-fill with existing values
    name = get_input("Display Name (alias):", default=db['name'])
    
    current_provider = db['provider']
    providers = manager.get_supported_providers()
    # Move current to top or just default selection
    provider = get_selection("Select Provider", [Choice(p, p) for p in providers], default=current_provider)
    
    params = db['params']
    host = get_input("Host:", default=params.get('host', 'localhost'))
    port = get_input("Port:", default=str(params.get('port', '')))
    user = get_input("Username:", default=params.get('user', ''))
    
    # Password: don't show current, just ask provided
    # If empty, keep existing? No, better explicit. 
    # Or asking "Keep existing?" functionality.
    # For now: if empty, keep existing.
    print_info("(Leave password empty to keep existing)")
    new_password = get_input("Password:")
    password = new_password if new_password else params.get('password', '')

    database = get_input("Database Name:", default=params.get('database', ''))

    # Backup Strategy Options
    # Backup Type removed (Full Only forced)
    
    retention = get_input("Retention (keep last N backups, 0=infinite):", default=str(db.get("retention", 0)))

    new_params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database
    }

    try:
        if manager.update_database(db_id, name, provider, new_params, int(retention)):
            print_success("Database configuration updated!")
        else:
            print_error("Failed to update.")
        get_input("Press Enter...")
    except Exception as e:
        print_error(f"Error: {e}")
        get_input("Press Enter...")

def restore_wizard(db_id: int):
    try:
        backups = manager.list_backups(db_id)
        if not backups:
            print_error("No backups found.")
            return

        choices = []
        for b in backups:
            label = f"{b['date'].strftime('%Y-%m-%d %H:%M')} | {b['filename']} ({b['size_mb']:.2f}MB)"
            choices.append(Choice(value=b['path'], name=label))
        
        choices.append(Separator())
        choices.append(Choice(value="cancel", name="Cancel"))

        backup_path = get_selection("Select Backup to Restore", choices)

        if backup_path == "cancel":
            return
        
        if get_confirm("WARNING: This will overwrite data. Continue?"):
            manager.restore_database(db_id, backup_path)
            print_success("Restored successfully.")
    except Exception as e:
        print_error(f"Restore failed: {e}")

def delete_database_wizard(db_id: int) -> bool:
    if get_confirm("Are you sure you want to delete this specific database config?"):
        manager.delete_database(db_id)
        print_success("Deleted.")
        return True
    return False

def schedule_wizard():
    dbs = manager.list_databases()
    if not dbs:
        print_info("No databases to schedule.")
        get_input("Press Enter...")
        return
        
    choices = [Choice(db['id'], db['name']) for db in dbs]
    choices.append(Choice("back", "Back"))
    
    db_id = get_selection("Select Database to Schedule", choices)
    if db_id == "back": return

    # Presets
    presets = [
        Choice("0 0 * * *", "Daily @ Midnight"),
        Choice("0 0 * * 0", "Weekly (Sunday)"),
        Choice("0 * * * *", "Hourly"),
        Choice("0 */6 * * *", "Every 6 Hours"),
        Choice("custom", "Custom Schedule")
    ]
    
    selected_schedule = get_selection("Select Schedule Preset", presets)
    
    if selected_schedule == "custom":
        print_info("Cron Format: * * * * * (min hour day month day_of_week)")
        schedule = get_input("Enter Cron Schedule:", "0 0 * * *")
    else:
        # Allow editing the preset? Or just confirm.
        # User asked for "standard settings... can be modified/confirmed"
        schedule = get_input("Confirm/Edit Schedule:", default=selected_schedule)
    
    try:
        cron_manager.add_backup_job(int(db_id), schedule)
        print_success("Schedule updated.")
        get_input("Press Enter...")
    except Exception as e:
        print_error(f"Error: {e}")
        get_input("Press Enter...")

if __name__ == "__main__":
    app()
