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
        
        console.print()
        
        choices = [
            Choice(value="config_sync", name="Configure Config Sync"),
            Choice(value="sync_now", name="Sync Config to S3 Now"),
            Choice(value="download", name="Download Config from S3"),
            Separator(),
            Choice(value="compression", name="Configure Compression"),
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
