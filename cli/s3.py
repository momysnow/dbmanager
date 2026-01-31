"""S3 bucket management menus and wizards"""
from rich.table import Table
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager
from utils.ui import (
    print_header, get_input, print_success, print_error, 
    print_info, get_confirm, get_selection
)

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
