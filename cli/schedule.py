"""Scheduling menus and wizards"""
from rich.table import Table
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager, cron_manager
from utils.ui import (
    print_header, get_input, print_success, print_error, 
    print_info, get_selection
)

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULING
# ═══════════════════════════════════════════════════════════════════════════════

def schedule_menu():
    while True:
        print_header()
        console.print("\n[bold cyan]═══ Scheduling ═══[/bold cyan]\n")
        
        choices = [
            Choice("add", "Schedule New Backup"),
            Choice("list", "List Scheduled Jobs"),
            Separator(),
            Choice("back", "Back to Main Menu")
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
        table.add_column("Status", style="green")
        for job in jobs:
            table.add_row(job["id"], job["schedule"], "Enabled" if job["enabled"] else "Disabled")
        console.print(table)
    get_input("Press Enter...")

def schedule_wizard():
    dbs = manager.list_databases()
    if not dbs:
        print_info("No databases to schedule.")
        get_input("Press Enter...")
        return
        
    choices = [Choice(db['id'], db['name']) for db in dbs]
    choices.append(Separator())
    choices.append(Choice("back", "Back"))
    
    db_id = get_selection("Select Database to Schedule", choices)
    if db_id == "back": return

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
        schedule = get_input("Confirm/Edit Schedule:", default=selected_schedule)
    
    try:
        cron_manager.add_backup_job(int(db_id), schedule)
        print_success("Schedule updated.")
        get_input("Press Enter...")
    except Exception as e:
        print_error(f"Error: {e}")
        get_input("Press Enter...")
