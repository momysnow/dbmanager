"""Settings menu"""
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager
from utils.ui import (
    print_header, get_input, print_success, print_error, 
    print_info, get_confirm, get_selection
)

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
        
        # Show compression status
        compression_settings = manager.config_manager.get_compression_settings()
        if compression_settings.get("enabled", False):
            algo = compression_settings.get("algorithm", "gzip")
            level = compression_settings.get("level", 6)
            console.print(f"[bold]Compression:[/bold] ✅ {algo.upper()} (level {level})")
        else:
            console.print(f"[bold]Compression:[/bold] ❌ Disabled")
        
        # Show encryption status
        encryption_settings = manager.config_manager.get_encryption_settings()
        if encryption_settings.get("enabled", False):
            has_password = encryption_settings.get("password") is not None
            status = "🔐 AES-256" if has_password else "⚠️  No password"
            console.print(f"[bold]Encryption:[/bold] ✅ {status}")
        else:
            console.print(f"[bold]Encryption:[/bold] ❌ Disabled")
        
        console.print()
        
        choices = [
            Choice(value="config_sync", name="Configure Config Sync"),
            Choice(value="sync_now", name="Sync Config to S3 Now"),
            Choice(value="download", name="Download Config from S3"),
            Separator(),
            Choice(value="export", name="📤 Export Configuration"),
            Choice(value="import", name="📥 Import Configuration"),
            Separator(),
            Choice(value="compression", name="Configure Compression"),
            Choice(value="encryption", name="Configure Encryption"),
            Choice(value="notifications", name="Configure Notifications"),
            Separator(),
            Choice(value="back", name="← Back to Main Menu"),
        ]
        
        action = get_selection("Settings Menu", choices)
        
        if action == "config_sync":
            buckets = manager.bucket_manager.list_buckets()
            if not buckets:
                print_info("No S3 buckets configured. Add one first in 'Manage S3 Buckets'.")
                get_input("Press Enter to continue...")
                continue
            
            bucket_choices = [
                Choice(value="back", name="← Back"),
                Separator(),
                Choice(value=None, name="Disable config sync"),
                Separator(),
            ] + [Choice(value=b['id'], name=f"{b['name']} ({b.get('bucket', '')})") for b in buckets]
            
            bucket_id = get_selection("Select bucket for config sync", bucket_choices)
            
            if bucket_id == "back":
                continue
            
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
            download_config_from_s3()
        
        elif action == "export":
            export_configuration()
        
        elif action == "import":
            import_configuration()
        
        elif action == "compression":
            compression_config_menu()
        
        elif action == "encryption":
            encryption_config_menu()
        
        elif action == "notifications":
            from cli.notifications import notification_menu
            notification_menu()
            
        elif action == "back":
            break


def export_configuration():
    """Export configuration wizard"""
    from utils.config_export import ConfigExporter
    from utils.ui import print_success, print_error
    
    print_header()
    console.print("\n[bold cyan]═══ Export Configuration ═══[/bold cyan]\n")
    
    include_backups = get_confirm("Include backup files in export?", default=False)
    output_path = get_input("Export path (leave empty for default):")
    
    try:
        exporter = ConfigExporter(manager.config_manager)
        
        if output_path and output_path.endswith('.json'):
            # JSON export (config only)
            path = exporter.export_to_json(output_path if output_path else None)
            print_success(f"Configuration exported to: {path}")
        else:
            # ZIP export
            path = exporter.export_config(
                output_path if output_path else None,
                include_backups=include_backups
            )
            print_success(f"Configuration exported to: {path}")
            
            if include_backups:
                console.print("[dim]Backup files included[/dim]")
    
    except Exception as e:
        print_error(f"Export failed: {e}")


def import_configuration():
    """Import configuration wizard"""
    from utils.config_export import ConfigExporter
    from utils.ui import print_success, print_error, print_info
    
    print_header()
    console.print("\n[bold cyan]═══ Import Configuration ═══[/bold cyan]\n")
    
    print_info("⚠️  Warning: This will modify your current configuration!")
    console.print()
    
    import_path = get_input("Import file path:")
    
    if not import_path:
        print_info("Import cancelled")
        return
    
    merge = get_confirm("Merge with existing configuration? (No = replace)", default=True)
    
    # Check if export includes backups
    from pathlib import Path
    import zipfile
    
    restore_backups = False
    if Path(import_path).suffix == '.zip':
        try:
            with zipfile.ZipFile(import_path, 'r') as zipf:
                if 'backups/' in zipf.namelist() or any('backups' in name for name in zipf.namelist()):
                    restore_backups = get_confirm("Export contains backups. Restore them?", default=False)
        except:
            pass
    
    if not get_confirm(f"Confirm import from {import_path}?", default=False):
        print_info("Import cancelled")
        return
    
    try:
        exporter = ConfigExporter(manager.config_manager)
        
        if import_path.endswith('.json'):
            summary = exporter.import_from_json(import_path, merge=merge)
        else:
            summary = exporter.import_config(import_path, merge=merge, restore_backups=restore_backups)
        
        print_success("Configuration imported successfully!")
        console.print(f"\n[bold]Import Summary:[/bold]")
        console.print(f"  Databases: {summary['databases_imported']}")
        console.print(f"  S3 Buckets: {summary['s3_buckets_imported']}")
        console.print(f"  Schedules: {summary['schedules_imported']}")
        
        if restore_backups:
            console.print(f"  Backups restored: {summary['backups_restored']}")
        
        if summary.get('errors'):
            console.print(f"\n[yellow]Errors:[/yellow]")
            for error in summary['errors']:
                console.print(f"  • {error}")
    
    except Exception as e:
        print_error(f"Import failed: {e}")

def compression_config_menu():
    """Configure compression settings"""
    from core.compression import get_available_algorithms, get_compression_info
    
    print_header()
    console.print("\n[bold cyan]═══ Configure Compression ═══[/bold cyan]\n")
    
    # Show available algorithms
    info = get_compression_info()
    console.print("[bold]Available Algorithms:[/bold]\n")
    for algo, details in info.items():
        status = "✅" if details['available'] else "❌"
        console.print(f"{status} [cyan]{algo.upper()}[/cyan]: {details['description']}")
        console.print(f"   Speed: {details['speed']} | Ratio: {details['ratio']} | Levels: {details['level_range']}\n")
    
    # Get current settings
    current = manager.config_manager.get_compression_settings()
    
    # Enable/Disable
    if get_confirm(f"Enable compression? (currently: {'enabled' if current.get('enabled') else 'disabled'})", 
                  default=current.get('enabled', False)):
        enabled = True
        
        # Select algorithm
        available = get_available_algorithms()
        algo_choices = [Choice(value=a, name=f"{a.upper()} - {info[a]['description']}") 
                       for a in available]
        
        algorithm = get_selection(
            f"Select compression algorithm (current: {current.get('algorithm', 'gzip')})",
            algo_choices
        )
        
        # Select level
        level_info = info[algorithm]['level_range']
        level = get_input(
            f"Compression level {level_info} (current: {current.get('level', 6)}): ",
            default=str(current.get('level', 6))
        )
        
        try:
            level = int(level)
        except:
            level = 6
        
        # Save settings
        manager.config_manager.update_compression_settings(
            enabled=True,
            algorithm=algorithm,
            level=level
        )
        print_success(f"Compression enabled: {algorithm.upper()} level {level}")
    else:
        manager.config_manager.update_compression_settings(enabled=False)
        print_success("Compression disabled")
    
    get_input("Press Enter to continue...")


def encryption_config_menu():
    """Configure encryption settings"""
    from core.encryption import is_encryption_available, get_encryption_info, generate_random_password
    
    print_header()
    console.print("\n[bold cyan]═══ Configure Encryption ═══[/bold cyan]\n")
    
    # Check if encryption is available
    if not is_encryption_available():
        console.print("[bold red]❌ Encryption not available[/bold red]\n")
        console.print("Install required library:")
        console.print("  pip install cryptography\n")
        get_input("Press Enter to continue...")
        return
    
    # Show encryption info
    info = get_encryption_info()
    console.print(f"[bold]Algorithm:[/bold] {info['algorithm']}")
    console.print(f"[bold]Key Derivation:[/bold] {info['key_derivation']}\n")
    
    console.print("[bold]Features:[/bold]")
    for feature in info['features']:
        console.print(f"  • {feature}")
    console.print()
    
    # Get current settings
    current = manager.config_manager.get_encryption_settings()
    
    # Enable/Disable
    if get_confirm(f"Enable encryption? (currently: {'enabled' if current.get('enabled') else 'disabled'})", 
                  default=current.get('enabled', False)):
        enabled = True
        
        # Get or set password
        console.print("\n[bold yellow]⚠️  Important: Store your password securely![/bold yellow]")
        console.print("Without the password, backups cannot be restored.\n")
        
        current_password = current.get('password')
        if current_password:
            console.print(f"[bold]Current password:[/bold] {'*' * 16} (set)")
            
            choices = [
                Choice(value="keep", name="Keep current password"),
                Choice(value="change", name="Change password"),
                Choice(value="generate", name="Generate new random password"),
            ]
            
            password_action = get_selection("Password options", choices)
            
            if password_action == "keep":
                password = current_password
            elif password_action == "change":
                password = get_input("Enter new encryption password: ")
                if not password:
                    print_info("No password provided, keeping current")
                    password = current_password
            else:  # generate
                password = generate_random_password(32)
                console.print(f"\n[bold green]Generated password:[/bold green]")
                console.print(f"[bold cyan]{password}[/bold cyan]\n")
                console.print("[bold yellow]⚠️  SAVE THIS PASSWORD! It cannot be recovered![/bold yellow]\n")
                get_input("Press Enter after saving the password...")
        else:
            console.print("[bold]No password set yet.[/bold]\n")
            
            choices = [
                Choice(value="manual", name="Enter password manually"),
                Choice(value="generate", name="Generate random password"),
            ]
            
            password_action = get_selection("Choose password method", choices)
            
            if password_action == "manual":
                password = get_input("Enter encryption password: ")
                if not password:
                    print_error("Password cannot be empty")
                    get_input("Press Enter to continue...")
                    return
            else:  # generate
                password = generate_random_password(32)
                console.print(f"\n[bold green]Generated password:[/bold green]")
                console.print(f"[bold cyan]{password}[/bold cyan]\n")
                console.print("[bold yellow]⚠️  SAVE THIS PASSWORD! It cannot be recovered![/bold yellow]\n")
                get_input("Press Enter after saving the password...")
        
        # Save settings
        manager.config_manager.update_encryption_settings(
            enabled=True,
            password=password
        )
        print_success("Encryption enabled with AES-256-GCM")
    else:
        manager.config_manager.update_encryption_settings(enabled=False)
        print_success("Encryption disabled")
    
    get_input("Press Enter to continue...")
