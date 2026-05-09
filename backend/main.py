"""DBManager CLI - Entry Point"""

import typer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager
from cli.database import manage_databases_menu, add_database_wizard
from cli.storage import manage_storage_targets_menu
from cli.schedule import schedule_menu
from cli.settings import settings_menu
from utils.ui import print_header, get_selection

app = typer.Typer()
proxy_app = typer.Typer(help="Manage the reverse proxy (Caddy)")
app.add_typer(proxy_app, name="proxy")


@proxy_app.command("bootstrap")
def proxy_bootstrap(
    force: bool = typer.Option(
        False, "--force", help="Reconfigure even if proxy.json exists"
    ),
) -> None:
    """First-run setup: env-driven or interactive wizard."""
    from proxy.wizard import bootstrap
    from proxy.runtime_print import print_runtime_config

    bootstrap(force=force)
    print_runtime_config()


@proxy_app.command("apply")
def proxy_apply() -> None:
    """Render Caddyfile + push to Caddy admin API (hot reload)."""
    from proxy.config import ProxyConfigManager
    from proxy.manager import ProxyManager

    mgr = ProxyConfigManager()
    if not mgr.exists():
        console.print("[red]proxy.json missing — run `proxy bootstrap` first[/red]")
        raise typer.Exit(code=1)
    result = ProxyManager(mgr).apply(mgr.load())
    console.print(result)


@proxy_app.command("status")
def proxy_status() -> None:
    from proxy.config import ProxyConfigManager
    from proxy.manager import ProxyManager

    mgr = ProxyConfigManager()
    cfg = mgr.load()
    console.print(ProxyManager(mgr).status(cfg))


@proxy_app.command("reload")
def proxy_reload() -> None:
    from proxy.config import ProxyConfigManager
    from proxy.manager import ProxyManager

    mgr = ProxyConfigManager()
    ok = ProxyManager(mgr).hot_reload(mgr.load())
    console.print("[green]reloaded[/green]" if ok else "[red]reload failed[/red]")


@proxy_app.command("restart")
def proxy_restart() -> None:
    from proxy.config import ProxyConfigManager
    from proxy.manager import ProxyManager

    mgr = ProxyConfigManager()
    ok = ProxyManager(mgr).restart_container(mgr.load())
    console.print("[green]restarted[/green]" if ok else "[red]restart failed[/red]")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


@app.command()
def perform_backup(
    db_id: int = typer.Option(..., help="ID of the database to backup"),
) -> None:
    """Internal command used by cron to perform scheduled backups."""
    try:
        path = manager.backup_database(db_id)
        print(f"Backup successful: {path}")
    except Exception as e:
        print(f"Backup failed: {e}")
        raise typer.Exit(code=1)


@app.command()
def start_api(
    background: bool = typer.Option(True, help="Run API in background"),
) -> None:
    """Start the REST API server as a daemon."""
    from utils.api_service import start_api_server, is_api_running

    if is_api_running():
        console.print("[yellow]⚠️  API server is already running[/yellow]")
        console.print("Use 'status-api' to check status or 'restart-api' to restart")
        return

    console.print("\n[bold cyan]🚀 Starting DBManager API Server...[/bold cyan]\n")

    if start_api_server(background=background):
        if background:
            console.print("[green]✅ API server started successfully[/green]")
            console.print("\nAPI available at: [bold]http://localhost:8000[/bold]")
            console.print("Swagger docs: [bold]http://localhost:8000/docs[/bold]")
            console.print("\nUse 'stop-api' to stop the server")
        else:
            console.print("[yellow]API server stopped[/yellow]")
    else:
        console.print("[red]❌ Failed to start API server[/red]")
        console.print("Check logs: ~/.dbmanager/api.log")


@app.command()
def stop_api() -> None:
    """Stop the REST API server."""
    from utils.api_service import stop_api_server, is_api_running

    if not is_api_running():
        console.print("[yellow]⚠️  API server is not running[/yellow]")
        return

    console.print("\n[bold cyan]🛑 Stopping DBManager API Server...[/bold cyan]\n")

    if stop_api_server():
        console.print("[green]✅ API server stopped successfully[/green]")
    else:
        console.print("[red]❌ Failed to stop API server[/red]")


@app.command()
def restart_api() -> None:
    """Restart the REST API server."""
    from utils.api_service import restart_api_server

    console.print("\n[bold cyan]🔄 Restarting DBManager API Server...[/bold cyan]\n")

    if restart_api_server():
        console.print("[green]✅ API server restarted successfully[/green]")
        console.print("\nAPI available at: [bold]http://localhost:8000[/bold]")
        console.print("Swagger docs: [bold]http://localhost:8000/docs[/bold]")
    else:
        console.print("[red]❌ Failed to restart API server[/red]")


@app.command()
def status_api() -> None:
    """Check REST API server status."""
    from utils.api_service import get_api_status

    status = get_api_status()

    console.print("\n[bold cyan]═══ API Server Status ═══[/bold cyan]\n")

    if status["running"]:
        console.print("[green]● Running[/green]")
        console.print(f"PID: {status['pid']}")
        console.print(f"URL: {status['url']}")
        console.print(f"Docs: {status['docs']}")
        if status["log_file"]:
            console.print(f"Logs: {status['log_file']}")
    else:
        console.print("[red]○ Stopped[/red]")
        console.print("\nStart with: python main.py start-api")

    console.print()


@app.command()
def interactive() -> None:
    """Starts the interactive shell mode."""
    while True:
        print_header()
        choices = [
            Choice(value="manage", name="Manage Databases"),
            Choice(value="add", name="Add Database"),
            Choice(value="schedule", name="Schedule Backups"),
            Choice(value="storage", name="Manage Storage Targets"),
            Choice(value="settings", name="Settings"),
            Separator(),
            Choice(value="api", name="🌐 Start REST API Server"),
            Separator(),
            Choice(value="exit", name="Exit"),
        ]

        action = get_selection("Main Menu", choices)

        if action == "dashboard":
            from cli.dashboard import dashboard_menu

            dashboard_menu()
        elif action == "manage":
            manage_databases_menu()
        elif action == "add":
            add_database_wizard()
        elif action == "schedule":
            schedule_menu()
        elif action == "storage":
            manage_storage_targets_menu()
        elif action == "settings":
            settings_menu()
        elif action == "api":
            # Call the start_api() command directly
            start_api(background=True)
        elif action == "exit":
            console.print("Goodbye!")
            break


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()
