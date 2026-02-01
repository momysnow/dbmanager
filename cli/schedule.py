"""Scheduling menus and wizards"""
from rich.table import Table
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager, cron_manager
from utils.ui import (
    print_header, get_input, print_success, print_error, 
    print_info, get_selection, get_confirm
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
            Choice("manage", "Manage Scheduled Jobs"),
            Separator(),
            Choice("back", "Back to Main Menu")
        ]
        action = get_selection("Scheduling Menu", choices)
        
        if action == "back": break
        elif action == "add": schedule_wizard()
        elif action == "list": list_jobs_wizard()
        elif action == "manage": manage_jobs_wizard()

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


def manage_jobs_wizard():
    jobs = cron_manager.list_jobs()
    if not jobs:
        print_info("No scheduled jobs to manage.")
        get_input("Press Enter...")
        return

    print_header()
    console.print("\n[bold cyan]═══ Manage Scheduled Jobs ═══[/bold cyan]\n")

    choices = [
        Choice(value="back", name="← Back"),
        Separator(),
    ] + [
        Choice(value=job["id"], name=f"DB {job['id']} | {job['schedule']} | {'Enabled' if job['enabled'] else 'Disabled'}")
        for job in jobs
    ]

    selected = get_selection("Select Job", choices)
    if selected == "back":
        return

    job = next((j for j in jobs if str(j.get("id")) == str(selected)), None)
    if not job:
        print_error("Job not found")
        get_input("Press Enter...")
        return

    actions = [
        Choice(value="edit", name="Edit Schedule"),
        Choice(value="toggle", name="Enable/Disable"),
        Choice(value="delete", name="Delete Job"),
        Separator(),
        Choice(value="back", name="← Back")
    ]
    action = get_selection("Job Actions", actions)
    if action == "back":
        return

    if action == "edit":
        new_schedule = _prompt_schedule(default=job["schedule"])
        if not new_schedule:
            return
        if cron_manager.update_schedule(int(job["id"]), new_schedule):
            print_success("Schedule updated.")
        else:
            print_error("Failed to update schedule")
        get_input("Press Enter...")

    elif action == "toggle":
        desired = not job["enabled"]
        if cron_manager.set_job_enabled(int(job["id"]), desired):
            print_success("Job enabled" if desired else "Job disabled")
        else:
            print_error("Failed to update job status")
        get_input("Press Enter...")

    elif action == "delete":
        if get_confirm("Delete this scheduled job?", default=False):
            cron_manager.remove_job(int(job["id"]))
            print_success("Job deleted")
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

    schedule = _prompt_schedule()
    if not schedule:
        return
    
    try:
        cron_manager.add_backup_job(int(db_id), schedule)
        print_success("Schedule updated.")
        get_input("Press Enter...")
    except Exception as e:
        print_error(f"Error: {e}")
        get_input("Press Enter...")


def _prompt_schedule(default: str = "0 0 * * *"):
    mode_choices = [
        Choice("simple", "Simple schedule (recommended)"),
        Choice("preset", "Preset cron"),
        Choice("custom", "Custom cron"),
        Choice("back", "← Back")
    ]
    mode = get_selection("Schedule Type", mode_choices)
    if mode == "back":
        return None

    if mode == "simple":
        return _simple_schedule_builder()

    if mode == "custom":
        print_info("Cron Format: * * * * * (min hour day month day_of_week)")
        return get_input("Enter Cron Schedule:", default)

    presets = [
        Choice("back", "← Back"),
        Separator(),
        Choice("0 0 * * *", "Daily @ Midnight"),
        Choice("0 0 * * 0", "Weekly (Sunday)"),
        Choice("0 * * * *", "Hourly"),
        Choice("0 */6 * * *", "Every 6 Hours"),
        Separator(),
        Choice("custom", "Custom Schedule")
    ]

    selected_schedule = get_selection("Select Schedule Preset", presets)
    if selected_schedule == "back":
        return None
    if selected_schedule == "custom":
        print_info("Cron Format: * * * * * (min hour day month day_of_week)")
        return get_input("Enter Cron Schedule:", default)
    return get_input("Confirm/Edit Schedule:", default=selected_schedule)


def _simple_schedule_builder():
    console.print("\n[bold]Simple schedule builder[/bold]")
    console.print("Choose frequency and time; we will build the cron expression.")

    freq_choices = [
        Choice("daily", "Daily"),
        Choice("weekly", "Weekly"),
        Choice("monthly", "Monthly"),
        Choice("hourly", "Every N hours"),
        Choice("back", "← Back")
    ]
    frequency = get_selection("Frequency", freq_choices)
    if frequency == "back":
        return None

    if frequency == "hourly":
        hours = get_input("Every how many hours?", "6")
        try:
            hours = int(hours)
            if hours < 1 or hours > 24:
                raise ValueError()
        except Exception:
            print_error("Invalid hour interval (1-24)")
            return None
        return f"0 */{hours} * * *"

    time_str = get_input("Time (HH:MM)", "02:00")
    try:
        hour_str, minute_str = time_str.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError()
    except Exception:
        print_error("Invalid time format")
        return None

    if frequency == "daily":
        return f"{minute} {hour} * * *"

    if frequency == "weekly":
        day_choices = [
            Choice("0", "Sunday"),
            Choice("1", "Monday"),
            Choice("2", "Tuesday"),
            Choice("3", "Wednesday"),
            Choice("4", "Thursday"),
            Choice("5", "Friday"),
            Choice("6", "Saturday"),
        ]
        day = get_selection("Day of week", day_choices)
        return f"{minute} {hour} * * {day}"

    if frequency == "monthly":
        day = get_input("Day of month (1-28)", "1")
        try:
            day = int(day)
            if day < 1 or day > 28:
                raise ValueError()
        except Exception:
            print_error("Invalid day of month (1-28)")
            return None
        return f"{minute} {hour} {day} * *"

    return None
