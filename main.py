import typer
import os
import tempfile
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
# DATABASE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def manage_databases_menu():
    while True:
        print_header()
        console.print("\n[bold cyan]═══ Manage Databases ═══[/bold cyan]\n")
        
        dbs = manager.list_databases()
        if not dbs:
            print_info("No databases configured.")
            get_input("Press Enter to return...")
            return

        # Show database table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Provider")
        table.add_column("Host")
        table.add_column("Local Ret.")
        table.add_column("S3")
        
        for db in dbs:
            s3_status = "✅" if db.get('s3_enabled') else "❌"
            table.add_row(
                str(db["id"]),
                db["name"],
                db["provider"],
                db["params"].get("host", "-"),
                str(db.get("retention", "∞")),
                s3_status
            )
        console.print(table)

        choices = []
        for db in dbs:
            name = f"{db['name']} ({db['provider']})"
            choices.append(Choice(value=db['id'], name=name))
        
        choices.append(Separator())
        choices.append(Choice(value="back", name="Back to Main Menu"))

        db_id = get_selection("Select a Database to Manage", choices)
        
        if db_id == "back":
            break
        
        db_actions_menu(int(db_id))

def db_actions_menu(db_id: int):
    while True:
        db = manager.config_manager.get_database(db_id)
        if not db:
            return

        print_header()
        console.print(f"\n[bold cyan]═══ Database: {db['name']} ═══[/bold cyan]\n")
        
        # Show S3 status
        if db.get('s3_enabled'):
            bucket = manager.bucket_manager.get_bucket(db.get('s3_bucket_id'))
            bucket_name = bucket.get('name') if bucket else 'Unknown'
            console.print(f"[bold]S3 Backups:[/bold] ✅ Enabled → {bucket_name}")
            console.print(f"[bold]S3 Retention:[/bold] {db.get('s3_retention', 0)}\n")
        else:
            console.print(f"[bold]S3 Backups:[/bold] ❌ Disabled\n")
        
        # Build menu based on features enabled
        choices = [
            Choice(value="check", name="Check Connection"),
            Choice(value="backup", name="Backup Now"),
            Separator("─── Backups ───"),
            Choice(value="list_local", name="List Local Backups"),
            Choice(value="restore", name="Restore from Local"),
        ]
        
        # Add S3 options if enabled
        if db.get('s3_enabled'):
            choices.extend([
                Choice(value="list_s3", name="List S3 Backups"),
                Choice(value="restore_s3", name="Restore from S3"),
            ])
        
        choices.extend([
            Separator("─── Config ───"),
            Choice(value="edit", name="Edit Configuration"),
            Choice(value="delete", name="Delete Database"),
            Separator(),
            Choice(value="back", name="Back to Databases List"),
        ])

        action = get_selection("Choose Action", choices)

        if action == "back":
            break
        elif action == "check":
            check_status(db_id)
            get_input("Press Enter to continue...")
        elif action == "edit":
            edit_database_wizard(db_id)
            db = manager.config_manager.get_database(db_id)  # Refresh
        elif action == "backup":
            perform_manual_backup(db_id)
            get_input("Press Enter to continue...")
        elif action == "list_local":
            list_local_backups(db_id)
            get_input("Press Enter to continue...")
        elif action == "list_s3":
            view_s3_backups(db_id)
            get_input("Press Enter to continue...")
        elif action == "restore":
            restore_wizard(db_id)
            get_input("Press Enter to continue...")
        elif action == "restore_s3":
            restore_from_s3_wizard(db_id)
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

def list_local_backups(db_id: int):
    """List local backups for a database"""
    console.print("\n[bold cyan]═══ Local Backups ═══[/bold cyan]\n")
    
    backups = manager.list_backups(db_id)
    if not backups:
        print_info("No local backups found")
        return
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim")
    table.add_column("Filename")
    table.add_column("Date")
    table.add_column("Size (MB)")
    
    for i, backup in enumerate(backups, 1):
        table.add_row(
            str(i),
            backup['filename'],
            backup['date'].strftime('%Y-%m-%d %H:%M'),
            f"{backup['size_mb']:.2f}"
        )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(backups)} backup(s)[/dim]")

def view_s3_backups(db_id: int):
    """View S3 backups for a database"""
    console.print("\n[bold cyan]═══ S3 Backups ═══[/bold cyan]\n")
    
    db = manager.config_manager.get_database(db_id)
    bucket_id = db.get('s3_bucket_id')
    
    if not bucket_id:
        print_error("No S3 bucket configured")
        return
    
    try:
        storage = manager.bucket_manager.get_storage(bucket_id)
        if not storage:
            print_error("Failed to connect to S3")
            return
        
        prefix = f"backups/{db_id}/"
        s3_backups = storage.list_files(prefix)
        
        if not s3_backups:
            print_info("No S3 backups found")
            return
        
        s3_backups = sorted(s3_backups, key=lambda x: x['last_modified'], reverse=True)
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim")
        table.add_column("Filename")
        table.add_column("Date")
        table.add_column("Size (MB)")
        
        for i, backup in enumerate(s3_backups, 1):
            filename = backup['key'].split('/')[-1]
            table.add_row(
                str(i),
                filename,
                str(backup['last_modified']),
                f"{backup['size'] / (1024 * 1024):.2f}"
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {len(s3_backups)} backup(s) on S3[/dim]")
    except Exception as e:
        print_error(f"Failed to list S3 backups: {e}")

def restore_wizard(db_id: int):
    try:
        backups = manager.list_backups(db_id)
        if not backups:
            print_error("No local backups found.")
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
        
        if get_confirm("⚠️  WARNING: This will overwrite data. Continue?"):
            manager.restore_database(db_id, backup_path)
            print_success("Restored successfully.")
    except Exception as e:
        print_error(f"Restore failed: {e}")

def restore_from_s3_wizard(db_id: int):
    """Restore database from S3 backup"""
    print_header()
    console.print("\n[bold cyan]═══ Restore from S3 ═══[/bold cyan]\n")
    
    db = manager.config_manager.get_database(db_id)
    bucket_id = db.get('s3_bucket_id')
    
    if not bucket_id:
        print_error("No S3 bucket configured")
        get_input("Press Enter to continue...")
        return
    
    try:
        storage = manager.bucket_manager.get_storage(bucket_id)
        if not storage:
            print_error("Failed to connect to S3")
            get_input("Press Enter to continue...")
            return
        
        prefix = f"backups/{db_id}/"
        s3_backups = storage.list_files(prefix)
        
        if not s3_backups:
            print_info("No S3 backups found")
            get_input("Press Enter to continue...")
            return
        
        s3_backups = sorted(s3_backups, key=lambda x: x['last_modified'], reverse=True)
        
        backup_choices = []
        for backup in s3_backups:
            filename = backup['key'].split('/')[-1]
            date_str = str(backup['last_modified'])[:19]
            size_mb = backup['size'] / (1024 * 1024)
            backup_choices.append(
                Choice(value=backup['key'], name=f"{filename} - {date_str} ({size_mb:.2f} MB)")
            )
        
        backup_choices.append(Separator())
        backup_choices.append(Choice(value="cancel", name="Cancel"))
        
        selected_key = get_selection("Select backup to restore", backup_choices)
        
        if selected_key == "cancel":
            return
        
        # Download to temp location
        console.print(f"\n[yellow]Downloading from S3...[/yellow]")
        temp_dir = tempfile.mkdtemp()
        local_path = os.path.join(temp_dir, selected_key.split('/')[-1])
        
        if storage.download_file(selected_key, local_path):
            console.print(f"[green]✅ Downloaded[/green]")
            
            if get_confirm(f"⚠️  This will REPLACE the current database. Continue?"):
                try:
                    manager.restore_database(db_id, local_path)
                    print_success("Database restored from S3!")
                except Exception as e:
                    print_error(f"Restore failed: {e}")
            
            # Cleanup
            try:
                os.remove(local_path)
                os.rmdir(temp_dir)
            except:
                pass
        else:
            print_error("Failed to download from S3")
        
    except Exception as e:
        print_error(f"Restore from S3 failed: {e}")
    
    get_input("Press Enter to continue...")

def delete_database_wizard(db_id: int) -> bool:
    if get_confirm("Are you sure you want to delete this database config?"):
        manager.delete_database(db_id)
        print_success("Deleted.")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE ADD/EDIT WIZARDS
# ═══════════════════════════════════════════════════════════════════════════════

def add_database_wizard():
    print_header()
    console.print("\n[bold cyan]═══ Add New Database ═══[/bold cyan]\n")
    
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
    
    # SQL Server specific options
    if provider == "sqlserver":
        trust_cert = get_confirm("Trust SSL Certificate?", default=True)
        params["trust_certificate"] = trust_cert
    
    retention = get_input("Local Retention (keep last N backups, 0=infinite):", default="0")
    
    # S3 Backup Options
    console.print("\n[bold cyan]S3 Backup Configuration[/bold cyan]")
    s3_enabled = get_confirm("Enable S3 backups?", default=False)
    s3_bucket_id = None
    s3_retention = 0
    
    if s3_enabled:
        buckets = manager.bucket_manager.list_buckets()
        if buckets:
            bucket_choices = [Choice(value=b['id'], name=f"{b['name']} ({b.get('bucket', '')})") for b in buckets]
            s3_bucket_id = get_selection("Select S3 bucket", bucket_choices)
            s3_retention_str = get_input("S3 Retention (keep last N backups on S3, 0=infinite):", default="0")
            s3_retention = int(s3_retention_str) if s3_retention_str else 0
        else:
            print_info("No S3 buckets configured. Add one in 'Manage S3 Buckets'.")
            s3_enabled = False

    try:
        db_id = manager.add_database(name, provider, params, int(retention) if retention else 0)
        
        # Update with S3 settings
        if s3_enabled:
            db_config = manager.config_manager.get_database(db_id)
            db_config['s3_enabled'] = s3_enabled
            db_config['s3_bucket_id'] = s3_bucket_id
            db_config['s3_retention'] = s3_retention
            manager.config_manager.save_config()
        
        print_success(f"Database added with ID {db_id}!")
        get_input("Press Enter...")
    except Exception as e:
        print_error(f"Failed: {e}")
        get_input("Press Enter...")

def edit_database_wizard(db_id: int):
    db = manager.config_manager.get_database(db_id)
    if not db: return

    print_header()
    console.print(f"\n[bold cyan]═══ Edit Database: {db['name']} ═══[/bold cyan]\n")

    name = get_input("Display Name (alias):", default=db['name'])
    
    current_provider = db['provider']
    providers = manager.get_supported_providers()
    provider = get_selection("Select Provider", [Choice(p, p) for p in providers], default=current_provider)
    
    params = db['params']
    host = get_input("Host:", default=params.get('host', 'localhost'))
    port = get_input("Port:", default=str(params.get('port', '')))
    user = get_input("Username:", default=params.get('user', ''))
    
    print_info("(Leave password empty to keep existing)")
    new_password = get_input("Password:")
    password = new_password if new_password else params.get('password', '')

    database = get_input("Database Name:", default=params.get('database', ''))
    retention = get_input("Local Retention (keep last N backups, 0=infinite):", default=str(db.get("retention", 0)))

    new_params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database
    }
    
    # SQL Server specific options
    if provider == "sqlserver":
        current_trust = params.get("trust_certificate", True)
        trust_cert = get_confirm("Trust SSL Certificate?", default=current_trust)
        new_params["trust_certificate"] = trust_cert
    
    # S3 Backup Options
    console.print("\n[bold cyan]S3 Backup Configuration[/bold cyan]")
    current_s3_enabled = db.get('s3_enabled', False)
    s3_enabled = get_confirm("Enable S3 backups?", default=current_s3_enabled)
    s3_bucket_id = None
    s3_retention = 0
    
    if s3_enabled:
        buckets = manager.bucket_manager.list_buckets()
        if buckets:
            bucket_choices = [Choice(value=b['id'], name=f"{b['name']} ({b.get('bucket', '')})") for b in buckets]
            current_bucket_id = db.get('s3_bucket_id')
            
            default_bucket = current_bucket_id if current_bucket_id in [b['id'] for b in buckets] else None
            s3_bucket_id = get_selection("Select S3 bucket", bucket_choices, default=default_bucket)
            
            current_s3_retention = db.get('s3_retention', 0)
            s3_retention_str = get_input("S3 Retention (keep last N backups on S3, 0=infinite):", default=str(current_s3_retention))
            s3_retention = int(s3_retention_str) if s3_retention_str else 0
        else:
            print_info("No S3 buckets configured. Add one in 'Manage S3 Buckets'.")
            s3_enabled = False

    try:
        if manager.update_database(db_id, name, provider, new_params, int(retention),
                                  s3_enabled, s3_bucket_id, s3_retention):
            print_success("Database configuration updated!")
        else:
            print_error("Failed to update.")
        get_input("Press Enter...")
    except Exception as e:
        print_error(f"Error: {e}")
        get_input("Press Enter...")

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

# ═══════════════════════════════════════════════════════════════════════════════
# S3 BUCKET MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def manage_s3_buckets_menu():
    """Menu for managing S3 bucket configurations"""
    while True:
        print_header()
        console.print("\n[bold cyan]═══ S3 Buckets ═══[/bold cyan]\n")
        
        buckets = manager.bucket_manager.list_buckets()
        
        if buckets:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="dim")
            table.add_column("Name")
            table.add_column("Provider")
            table.add_column("Bucket")
            table.add_column("Endpoint")
            
            for bucket in buckets:
                endpoint = bucket.get('endpoint_url', 'AWS S3')
                table.add_row(
                    str(bucket['id']),
                    bucket['name'],
                    bucket.get('provider', 's3'),
                    bucket.get('bucket', ''),
                    endpoint
                )
            
            console.print(table)
        else:
            print_info("No S3 buckets configured")
        
        choices = [
            Choice(value="add", name="Add New Bucket"),
        ]
        
        if buckets:
            choices.insert(1, Choice(value="manage", name="Manage Bucket"))
        
        choices.extend([
            Separator(),
            Choice(value="back", name="Back to Main Menu"),
        ])
        
        action = get_selection("S3 Buckets Menu", choices)
        
        if action == "add":
            add_s3_bucket_wizard()
        elif action == "manage":
            if buckets:
                bucket_choices = [Choice(value=b['id'], name=f"{b['name']} ({b.get('bucket', '')})") for b in buckets]
                bucket_id = get_selection("Select bucket to manage", bucket_choices)
                manage_single_bucket(bucket_id)
        elif action == "back":
            break

def manage_single_bucket(bucket_id: int):
    """Manage a single S3 bucket"""
    while True:
        bucket = manager.bucket_manager.get_bucket(bucket_id)
        if not bucket:
            print_error("Bucket not found")
            get_input("Press Enter to continue...")
            return
        
        print_header()
        console.print(f"\n[bold cyan]═══ Bucket: {bucket['name']} ═══[/bold cyan]\n")
        
        # Display bucket details
        console.print(f"[bold]Provider:[/bold] {bucket.get('provider', 's3')}")
        console.print(f"[bold]Bucket:[/bold] {bucket.get('bucket', '')}")
        console.print(f"[bold]Endpoint:[/bold] {bucket.get('endpoint_url', 'AWS S3')}")
        console.print(f"[bold]Region:[/bold] {bucket.get('region', 'us-east-1')}")
        console.print()
        
        choices = [
            Choice(value="test", name="Test Connection"),
            Choice(value="edit", name="Edit Bucket"),
            Choice(value="delete", name="Delete Bucket"),
            Separator(),
            Choice(value="back", name="Back to Buckets List"),
        ]
        
        action = get_selection("Bucket Actions", choices)
        
        if action == "test":
            console.print("\n[yellow]Testing connection...[/yellow]")
            if manager.bucket_manager.test_bucket(bucket_id):
                print_success("✅ Connection successful!")
            else:
                print_error("❌ Connection failed")
            get_input("Press Enter to continue...")
        elif action == "edit":
            edit_s3_bucket_wizard(bucket_id)
        elif action == "delete":
            if get_confirm(f"Delete bucket '{bucket['name']}'?"):
                if manager.bucket_manager.delete_bucket(bucket_id):
                    print_success("Bucket deleted")
                    get_input("Press Enter to continue...")
                    break
                else:
                    print_error("Failed to delete bucket (may be in use)")
                    get_input("Press Enter to continue...")
        elif action == "back":
            break

def add_s3_bucket_wizard():
    """Wizard for adding S3 bucket configuration"""
    print_header()
    console.print("\n[bold cyan]═══ Add S3 Bucket ═══[/bold cyan]\n")
    
    name = get_input("Bucket name (display name)")
    if not name:
        print_info("Cancelled")
        get_input("Press Enter to continue...")
        return
    
    provider_choices = [
        Choice(value="minio", name="Minio"),
        Choice(value="garage", name="Garage"),
        Choice(value="s3", name="Amazon S3"),
        Choice(value="other", name="Other S3-compatible"),
    ]
    provider = get_selection("Select provider", provider_choices)
    
    bucket_name = get_input("S3 Bucket name")
    if not bucket_name:
        print_info("Cancelled")
        get_input("Press Enter to continue...")
        return
    
    access_key = get_input("Access Key")
    if not access_key:
        print_info("Cancelled")
        get_input("Press Enter to continue...")
        return
    
    console.print("[dim]Note: Secret key will not be displayed[/dim]")
    secret_key = get_input("Secret Key")
    if not secret_key:
        print_info("Cancelled")
        get_input("Press Enter to continue...")
        return
    
    endpoint_url = None
    if provider != "s3":
        endpoint_url = get_input(f"{provider.capitalize()} endpoint URL (e.g., http://192.168.1.26:9000)")
        if not endpoint_url:
            print_info("Cancelled")
            get_input("Press Enter to continue...")
            return
    
    region = get_input("Region", default="us-east-1")
    
    bucket_config = {
        'name': name,
        'provider': provider,
        'bucket': bucket_name,
        'access_key': access_key,
        'secret_key': secret_key,
        'region': region
    }
    
    if endpoint_url:
        bucket_config['endpoint_url'] = endpoint_url
    
    # Test connection before saving
    console.print("\n[yellow]Testing connection...[/yellow]")
    from core.s3_storage import S3Storage
    try:
        test_storage = S3Storage(bucket_config)
        if test_storage.test_connection():
            print_success("✅ Connection successful!")
            bucket_id = manager.bucket_manager.add_bucket(bucket_config)
            print_success(f"S3 bucket added with ID {bucket_id}")
        else:
            print_error("❌ Connection test failed. Bucket not saved.")
    except Exception as e:
        print_error(f"❌ Connection test failed: {e}")
    
    get_input("Press Enter to continue...")

def edit_s3_bucket_wizard(bucket_id: int):
    """Editor for existing S3 bucket configuration"""
    bucket = manager.bucket_manager.get_bucket(bucket_id)
    if not bucket:
        print_error("Bucket not found")
        return
    
    print_header()
    console.print(f"\n[bold cyan]═══ Edit S3 Bucket: {bucket['name']} ═══[/bold cyan]\n")
    
    name = get_input("Bucket name (display name)", default=bucket.get('name', ''))
    if not name:
        name = bucket.get('name')
    
    providers = ["minio", "garage", "s3", "other"]
    current_provider = bucket.get('provider', 's3')
    provider_choices = [Choice(value=p, name=p.capitalize()) for p in providers]
    provider = get_selection("Select provider", provider_choices, default=current_provider)
    
    bucket_name = get_input("S3 Bucket name", default=bucket.get('bucket', ''))
    if not bucket_name:
        bucket_name = bucket.get('bucket')
    
    console.print("[dim]Leave empty to keep current credentials[/dim]")
    access_key = get_input("Access Key")
    if not access_key:
        access_key = bucket.get('access_key')
    
    secret_key = get_input("Secret Key")
    if not secret_key:
        secret_key = bucket.get('secret_key')
    
    if provider != "s3":
        endpoint_url = get_input("Endpoint URL", default=bucket.get('endpoint_url', ''))
    else:
        endpoint_url = None
    
    region = get_input("Region", default=bucket.get('region', 'us-east-1'))
    
    updated_config = {
        'name': name,
        'provider': provider,
        'bucket': bucket_name,
        'access_key': access_key,
        'secret_key': secret_key,
        'region': region
    }
    
    if endpoint_url:
        updated_config['endpoint_url'] = endpoint_url
    
    # Test connection
    console.print("\n[yellow]Testing updated configuration...[/yellow]")
    from core.s3_storage import S3Storage
    try:
        test_storage = S3Storage(updated_config)
        if test_storage.test_connection():
            print_success("✅ Connection successful!")
            if manager.bucket_manager.update_bucket(bucket_id, updated_config):
                print_success("Bucket configuration updated!")
            else:
                print_error("Failed to save configuration")
        else:
            print_error("❌ Connection test failed. Changes not saved.")
    except Exception as e:
        print_error(f"❌ Test failed: {e}")
    
    get_input("Press Enter to continue...")

# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS MENU
# ═══════════════════════════════════════════════════════════════════════════════

def settings_menu():
    """Settings menu for config sync and other options"""
    while True:
        print_header()
        console.print("\n[bold cyan]═══ Settings ═══[/bold cyan]\n")
        
        # Show current config sync status
        current_bucket_id = manager.config_sync.get_config_bucket_id()
        if current_bucket_id:
            bucket_name = manager.bucket_manager.get_bucket_name(current_bucket_id)
            console.print(f"[bold]Config Sync:[/bold] ✅ Enabled → {bucket_name}")
        else:
            console.print(f"[bold]Config Sync:[/bold] ❌ Disabled")
        
        console.print()
        
        choices = [
            Choice(value="config_sync", name="Configure Config Sync"),
            Choice(value="sync_now", name="Sync Config to S3 Now"),
            Choice(value="download", name="Download Config from S3"),
            Separator(),
            Choice(value="back", name="Back to Main Menu"),
        ]
        
        action = get_selection("Settings Menu", choices)
        
        if action == "config_sync":
            buckets = manager.bucket_manager.list_buckets()
            if not buckets:
                print_info("No S3 buckets configured. Add one first in 'Manage S3 Buckets'.")
                get_input("Press Enter to continue...")
                continue
            
            bucket_choices = [
                Choice(value=None, name="Disable config sync"),
                Separator(),
            ] + [Choice(value=b['id'], name=f"{b['name']} ({b.get('bucket', '')})") for b in buckets]
            
            bucket_id = get_selection("Select bucket for config sync", bucket_choices)
            manager.config_sync.set_config_bucket(bucket_id)
            
            if bucket_id:
                print_success(f"Config sync enabled")
                if get_confirm("Upload config to S3 now?"):
                    manager.config_sync.sync_to_s3()
            else:
                print_success("Config sync disabled")
            
            get_input("Press Enter to continue...")
            
        elif action == "sync_now":
            if current_bucket_id:
                console.print("[yellow]Syncing config to S3...[/yellow]")
                manager.config_sync.sync_to_s3()
                print_success("Config synced!")
            else:
                print_info("Config sync not configured")
            get_input("Press Enter to continue...")
            
        elif action == "download":
            if current_bucket_id:
                console.print("[yellow]Downloading config from S3...[/yellow]")
                manager.config_sync.sync_from_s3()
            else:
                print_info("Config sync not configured")
            get_input("Press Enter to continue...")
            
        elif action == "back":
            break

# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()
