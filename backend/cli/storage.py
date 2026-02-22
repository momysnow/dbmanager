"""Storage target management menus and wizards"""

from typing import Any, Optional

from rich.table import Table
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager
from utils.ui import (
    print_header,
    get_input,
    print_success,
    print_error,
    print_info,
    get_confirm,
    get_selection,
)

# ═══════════════════════════════════════════════════════════════════════════════
# STORAGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════


def manage_storage_targets_menu() -> None:
    """Menu for managing storage target configurations"""
    while True:
        print_header()
        console.print("\n[bold cyan]═══ Storage Targets ═══[/bold cyan]\n")

        targets = manager.storage_manager.list_storage()

        if targets:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="dim")
            table.add_column("Name")
            table.add_column("Provider")
            table.add_column("Details")

            for target in targets:
                # Format details based on provider
                details = target.get("bucket", "")
                if target.get("provider") == "smb":
                    details = f"{target.get('share_name')} @ {target.get('server')}"

                table.add_row(
                    str(target["id"]),
                    target["name"],
                    target.get("provider", "s3"),
                    details,
                )

            console.print(table)
        else:
            print_info("No storage targets configured")

        choices: list[Any] = [
            Choice(value="add", name="Add New Storage Target"),
        ]

        if targets:
            choices.insert(1, Choice(value="manage", name="Manage Target"))

        choices.extend(
            [
                Separator(),
                Choice(value="back", name="Back to Main Menu"),
            ]
        )

        action = get_selection("Storage Targets Menu", choices)

        if action == "add":
            add_storage_target_wizard()
        elif action == "manage":
            if targets:
                target_choices: list[Any] = [
                    Choice(value="back", name="← Back"),
                    Separator(),
                ] + [Choice(value=t["id"], name=t["name"]) for t in targets]
                target_id = get_selection("Select target to manage", target_choices)
                if target_id != "back":
                    manage_single_target(target_id)
        elif action == "back":
            break


def manage_single_target(target_id: int) -> None:
    """Manage a single storage target"""
    while True:
        target = manager.storage_manager.get_storage_config(target_id)
        if not target:
            print_error("Storage target not found")
            get_input("Press Enter to continue...")
            return

        print_header()
        console.print(f"\n[bold cyan]═══ Target: {target['name']} ═══[/bold cyan]\n")

        # Display details
        provider = target.get("provider", "s3")
        console.print(f"[bold]Provider:[/bold] {provider}")

        if provider == "smb":
            console.print(f"[bold]Server:[/bold] {target.get('server')}")
            console.print(f"[bold]Share:[/bold] {target.get('share_name')}")
            console.print(f"[bold]Path:[/bold] {target.get('remote_path', '/')}")
            console.print(f"[bold]Username:[/bold] {target.get('smb_username')}")
        else:
            console.print(f"[bold]Bucket:[/bold] {target.get('bucket', '')}")
            console.print(
                f"[bold]Endpoint:[/bold] {target.get('endpoint_url', 'AWS S3')}"
            )
            console.print(f"[bold]Region:[/bold] {target.get('region', 'us-east-1')}")

        console.print()

        choices: list[Any] = [
            Choice(value="test", name="Test Connection"),
            Choice(value="edit", name="Edit Target"),
            Choice(value="delete", name="Delete Target"),
            Separator(),
            Choice(value="back", name="Back to Target List"),
        ]

        action = get_selection("Target Actions", choices)

        if action == "test":
            console.print("\n[yellow]Testing connection...[/yellow]")
            try:
                # Use manager factory primarily, or manual instance if needed
                # But manager.get_storage needs an ID, and we have it.
                # However, if we are editing, we might want to test BEFORE saving.
                # Here we are just "managing" an existing one, so get_storage works.
                storage_instance = manager.storage_manager.get_storage(target_id)
                if storage_instance and storage_instance.test_connection():
                    print_success("✅ Connection successful!")
                else:
                    print_error("❌ Connection failed (Check logs/config)")
            except Exception as e:
                print_error(f"❌ Connection error: {e}")

            get_input("Press Enter to continue...")
        elif action == "edit":
            edit_storage_target_wizard(target_id)
        elif action == "delete":
            if get_confirm(f"Delete target '{target['name']}'?"):
                if manager.storage_manager.delete_storage(target_id):
                    print_success("Target deleted")
                    get_input("Press Enter to continue...")
                    break
                else:
                    print_error("Failed to delete target (may be in use)")
                    get_input("Press Enter to continue...")
        elif action == "back":
            break


def add_storage_target_wizard() -> None:
    """Wizard for adding storage target configuration"""
    print_header()
    console.print("\n[bold cyan]═══ Add Storage Target ═══[/bold cyan]\n")

    name = get_input("Target Name (display name)")
    if not name:
        print_info("Cancelled")
        get_input("Press Enter to continue...")
        return

    provider_choices = [
        Choice(value="minio", name="Minio (S3 Compatible)"),
        Choice(value="garage", name="Garage (S3 Compatible)"),
        Choice(value="s3", name="Amazon S3"),
        Choice(value="other", name="Other S3-compatible"),
        Separator(),
        Choice(value="smb", name="SMB / CIFS (Windows Share)"),
    ]
    provider = get_selection("Select provider", provider_choices)

    config = {
        "name": name,
        "provider": provider,
    }

    if provider == "smb":
        server = get_input("Server Address (Hostname or IP)")
        share_name = get_input("Share Name")
        username = get_input("Username")
        password = get_input("Password")

        if not server or not share_name or not username or not password:
            print_info("Cancelled (missing required fields)")
            get_input("Press Enter to continue...")
            return

        config.update(
            {
                "server": server,
                "share_name": share_name,
                "smb_username": username,
                "smb_password": password,
                "remote_path": "/",  # Default
            }
        )

    else:
        # S3 based
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
            endpoint_url = get_input(
                f"{provider.capitalize()} endpoint URL (e.g., http://192.168.1.26:9000)"
            )
            if not endpoint_url:
                print_info("Cancelled")
                get_input("Press Enter to continue...")
                return

        region = get_input("Region", default="us-east-1")

        config.update(
            {
                "bucket": bucket_name,
                "access_key": access_key,
                "secret_key": secret_key,
                "region": region,
            }
        )
        if endpoint_url:
            config["endpoint_url"] = endpoint_url

    # Test connection before saving
    console.print("\n[yellow]Testing connection...[/yellow]")

    try:
        # Use factory from manager to get correct provider class/instance
        # We need to instantiate it manually to test BEFORE saving to config
        # Use factory from manager to get correct provider class/instance
        # We need to instantiate it manually to test BEFORE saving to config
        # We can't use manager.get_storage because it looks up by ID from config.
        # We need to construct the provider directly.
        # BUT StorageManager logic is nice to encapsulate.
        # Let's peek at provider map if possible or just import known ones.
        # Ideally StorageManager has a `get_provider_class` method or we import them.

        # Simplified approach: Use StorageManager's map if exposed or import here
        from core.s3_storage import S3Storage
        from core.storage_provider import StorageProvider

        # For SMB, we will need to import it later when created

        test_provider: Optional[StorageProvider] = None
        if provider == "smb":
            try:
                from core.smb_storage import SMBStorage

                test_provider = SMBStorage(config)
            except ImportError:
                print_error("SMB support not installed or implemented yet.")
        else:
            test_provider = S3Storage(config)

        if test_provider and test_provider.test_connection():
            print_success("✅ Connection successful!")
            target_id = manager.storage_manager.add_storage(config)
            print_success(f"Storage target added with ID {target_id}")
        else:
            print_error("❌ Connection test failed. Target not saved.")
    except Exception as e:
        print_error(f"❌ Connection test failed: {e}")

    get_input("Press Enter to continue...")


def edit_storage_target_wizard(target_id: int) -> None:
    """Editor for existing storage configuration"""
    target = manager.storage_manager.get_storage_config(target_id)
    if not target:
        print_error("Target not found")
        return

    print_header()
    console.print(f"\n[bold cyan]═══ Edit Target: {target['name']} ═══[/bold cyan]\n")

    name = get_input("Target Name", default=target.get("name", ""))
    if not name:
        name = str(target.get("name") or "")

    current_provider = target.get("provider", "s3")
    # For simplicity, not allowing provider change in edit for now to avoid field mess
    # or we can allow it but it basically resets fields.
    # Let's keep it simple: can't change provider easily without re-entering all auth.
    console.print(f"Provider: [bold]{current_provider}[/bold]")

    updated_config = target.copy()
    updated_config["name"] = name

    if current_provider == "smb":
        server = get_input("Server", default=target.get("server", ""))
        share_name = get_input("Share Name", default=target.get("share_name", ""))

        console.print("[dim]Leave empty to keep current[/dim]")
        username = get_input("Username", default=target.get("smb_username", ""))
        password = get_input("Password")  # Don't show default for password

        updated_config["server"] = server
        updated_config["share_name"] = share_name
        updated_config["smb_username"] = username
        if password:
            updated_config["smb_password"] = password

    else:
        # S3
        bucket_name = get_input("S3 Bucket name", default=target.get("bucket", ""))
        updated_config["bucket"] = bucket_name

        console.print("[dim]Leave empty to keep current[/dim]")
        access_key = get_input("Access Key", default=target.get("access_key", ""))
        updated_config["access_key"] = access_key

        secret_key = get_input("Secret Key")
        if secret_key:
            updated_config["secret_key"] = secret_key

        if current_provider != "s3":
            endpoint_url = get_input(
                "Endpoint URL", default=target.get("endpoint_url", "")
            )
            updated_config["endpoint_url"] = endpoint_url

        region = get_input("Region", default=target.get("region", "us-east-1"))
        updated_config["region"] = region

    # Test connection
    console.print("\n[yellow]Testing updated configuration...[/yellow]")

    try:
        from core.s3_storage import S3Storage
        from core.storage_provider import StorageProvider

        test_provider: Optional[StorageProvider] = None

        if current_provider == "smb":
            try:
                from core.smb_storage import SMBStorage

                test_provider = SMBStorage(updated_config)
            except ImportError:
                print_error("SMB support not installed.")
        else:
            test_provider = S3Storage(updated_config)

        if test_provider and test_provider.test_connection():
            print_success("✅ Connection successful!")
            if manager.storage_manager.update_storage(target_id, updated_config):
                print_success("Target configuration updated!")
            else:
                print_error("Failed to save configuration")
        else:
            print_error("❌ Connection test failed. Changes not saved.")
    except Exception as e:
        print_error(f"❌ Test failed: {e}")

    get_input("Press Enter to continue...")
