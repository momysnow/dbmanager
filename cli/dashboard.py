"""Dashboard CLI menu"""

from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from datetime import datetime

from cli import console, manager
from utils.ui import print_header, get_selection, get_input
from utils.stats import DashboardStats


def dashboard_menu():
    """Display dashboard statistics"""
    stats = DashboardStats(manager.config_manager, manager)
    
    while True:
        print_header()
        console.print("\n[bold cyan]═══ Dashboard ═══[/bold cyan]\n")
        
        choices = [
            Choice(value="overview", name="📊 Overview"),
            Choice(value="databases", name="💾 Database Statistics"),
            Choice(value="recent", name="📅 Recent Activity"),
            Choice(value="storage", name="💿 Storage Breakdown"),
            Choice(value="health", name="🏥 Health Status"),
            Separator(),
            Choice(value="back", name="← Back"),
        ]
        
        action = get_selection("Dashboard", choices)
        
        if action == "back":
            break
        elif action == "overview":
            show_overview(stats)
        elif action == "databases":
            show_database_stats(stats)
        elif action == "recent":
            show_recent_activity(stats)
        elif action == "storage":
            show_storage_breakdown(stats)
        elif action == "health":
            show_health_status(stats)
        
        get_input("\nPress Enter to continue...")


def show_overview(stats: DashboardStats):
    """Show overview statistics"""
    print_header()
    console.print("\n[bold cyan]═══ Overview Statistics ═══[/bold cyan]\n")
    
    data = stats.get_overview_stats()
    
    # Create table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold white")
    
    table.add_row("📊 Total Databases", str(data['total_databases']))
    table.add_row("☁️  S3 Buckets", str(data['total_s3_buckets']))
    table.add_row("⏰ Total Schedules", str(data['total_schedules']))
    table.add_row("✅ Active Schedules", str(data['active_schedules']))
    table.add_row("💾 Total Backups", str(data['total_backups']))
    table.add_row("📦 Total Backup Size", f"{data['total_backup_size_gb']:.2f} GB")
    
    console.print(table)


def show_database_stats(stats: DashboardStats):
    """Show per-database statistics"""
    print_header()
    console.print("\n[bold cyan]═══ Database Statistics ═══[/bold cyan]\n")
    
    data = stats.get_database_stats()
    
    if not data:
        console.print("[yellow]No databases configured[/yellow]")
        return
    
    # Create table
    table = Table(show_header=True)
    table.add_column("Database", style="cyan")
    table.add_column("Provider", style="blue")
    table.add_column("Backups", justify="right")
    table.add_column("Size (GB)", justify="right")
    table.add_column("Last Backup", style="green")
    table.add_column("Schedule", justify="center")
    table.add_column("S3", justify="center")
    
    for db_stat in data:
        last_backup = db_stat['last_backup_date'].strftime("%Y-%m-%d %H:%M") if db_stat['last_backup_date'] else "Never"
        schedule_icon = "✅" if db_stat['has_schedule'] else "❌"
        s3_icon = "☁️" if db_stat['s3_enabled'] else "—"
        
        table.add_row(
            db_stat['name'],
            db_stat['provider'].upper(),
            str(db_stat['backup_count']),
            f"{db_stat['total_size_mb'] / 1024:.2f}",
            last_backup,
            schedule_icon,
            s3_icon
        )
    
    console.print(table)


def show_recent_activity(stats: DashboardStats):
    """Show recent backup activity"""
    print_header()
    console.print("\n[bold cyan]═══ Recent Activity (Last 7 Days) ═══[/bold cyan]\n")
    
    data = stats.get_recent_activity(days=7)
    
    console.print(f"[bold]Total recent backups:[/bold] {data['total_recent_backups']}\n")
    
    if not data['recent_backups']:
        console.print("[yellow]No recent backups[/yellow]")
        return
    
    # Create table
    table = Table(show_header=True)
    table.add_column("Database", style="cyan")
    table.add_column("Date", style="green")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Filename", style="dim")
    
    for backup in data['recent_backups']:
        table.add_row(
            backup['database'],
            backup['date'].strftime("%Y-%m-%d %H:%M"),
            f"{backup['size_mb']:.2f}",
            backup['filename']
        )
    
    console.print(table)


def show_storage_breakdown(stats: DashboardStats):
    """Show storage usage breakdown"""
    print_header()
    console.print("\n[bold cyan]═══ Storage Breakdown ═══[/bold cyan]\n")
    
    data = stats.get_storage_breakdown()
    
    console.print(f"[bold]Total Storage:[/bold] {data['total_size_gb']:.2f} GB\n")
    
    if not data['breakdown']:
        console.print("[yellow]No backups found[/yellow]")
        return
    
    # Create table with progress bars
    table = Table(show_header=True)
    table.add_column("Database", style="cyan")
    table.add_column("Size (GB)", justify="right")
    table.add_column("Backups", justify="right")
    table.add_column("Usage", style="green")
    
    for item in data['breakdown']:
        # Create ASCII progress bar
        bar_length = 20
        filled = int(item['percentage'] / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        table.add_row(
            item['database'],
            f"{item['size_gb']:.2f}",
            str(item['backup_count']),
            f"{bar} {item['percentage']:.1f}%"
        )
    
    console.print(table)


def show_health_status(stats: DashboardStats):
    """Show system health status"""
    print_header()
    console.print("\n[bold cyan]═══ Health Status ═══[/bold cyan]\n")
    
    data = stats.get_health_status()
    
    # Overall status
    if data['status'] == 'healthy':
        console.print("[bold green]✅ System Healthy[/bold green]\n")
    elif data['status'] == 'warning':
        console.print("[bold yellow]⚠️  System Has Warnings[/bold yellow]\n")
    else:
        console.print("[bold red]❌ System Has Critical Issues[/bold red]\n")
    
    # Issues
    if data['issues']:
        console.print("[bold red]Critical Issues:[/bold red]")
        for issue in data['issues']:
            console.print(f"  • {issue}")
        console.print()
    
    # Warnings
    if data['warnings']:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for warning in data['warnings']:
            console.print(f"  • {warning}")
        console.print()
    
    if not data['issues'] and not data['warnings']:
        console.print("✅ All systems operational")
        console.print("  • All databases have recent backups")
        console.print("  • All databases have active schedules")
