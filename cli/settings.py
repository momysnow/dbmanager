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
            if current_bucket_id:
                console.print("[yellow]Downloading config from S3...[/yellow]")
                manager.config_sync.sync_from_s3()
            else:
                print_info("Config sync not configured")
            get_input("Press Enter to continue...")
        
        elif action == "compression":
            compression_config_menu()
        
        elif action == "encryption":
            encryption_config_menu()
        
        elif action == "notifications":
            from cli.notifications import notification_menu
            notification_menu()
            
        elif action == "back":
            break


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
