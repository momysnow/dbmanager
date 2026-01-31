"""Notification settings menu"""

from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager
from utils.ui import print_header, get_selection, get_input, get_confirm, print_success, print_error, print_info


def notification_menu():
    """Configure notification settings"""
    while True:
        print_header()
        console.print("\n[bold cyan]═══ Notification Settings ═══[/bold cyan]\n")
        
        # Get current settings
        email_settings = manager.config_manager.get_notification_settings("email")
        slack_settings = manager.config_manager.get_notification_settings("slack")
        teams_settings = manager.config_manager.get_notification_settings("teams")
        discord_settings = manager.config_manager.get_notification_settings("discord")
        
        # Show status
        console.print(f"[bold]Email:[/bold] {'✅ Enabled' if email_settings.get('enabled') else '❌ Disabled'}")
        console.print(f"[bold]Slack:[/bold] {'✅ Enabled' if slack_settings.get('enabled') else '❌ Disabled'}")
        console.print(f"[bold]Teams:[/bold] {'✅ Enabled' if teams_settings.get('enabled') else '❌ Disabled'}")
        console.print(f"[bold]Discord:[/bold] {'✅ Enabled' if discord_settings.get('enabled') else '❌ Disabled'}")
        console.print()
        
        choices = [
            Choice(value="email", name="📧 Configure Email (SMTP)"),
            Choice(value="slack", name="💬 Configure Slack Webhook"),
            Choice(value="teams", name="👔 Configure Microsoft Teams Webhook"),
            Choice(value="discord", name="🎮 Configure Discord Webhook"),
            Separator(),
            Choice(value="test", name="🧪 Test Notifications"),
            Separator(),
            Choice(value="back", name="← Back"),
        ]
        
        action = get_selection("Notification Settings", choices)
        
        if action == "back":
            break
        elif action == "email":
            configure_email_notifications()
        elif action == "slack":
            configure_slack_notifications()
        elif action == "teams":
            configure_teams_notifications()
        elif action == "discord":
            configure_discord_notifications()
        elif action == "test":
            test_notifications()
        
        get_input("\nPress Enter to continue...")


def configure_email_notifications():
    """Configure email notification settings"""
    print_header()
    console.print("\n[bold cyan]═══ Email Notifications (SMTP) ═══[/bold cyan]\n")
    
    current = manager.config_manager.get_notification_settings("email")
    
    # Enable/Disable
    enabled = get_confirm(
        f"Enable email notifications? (currently: {'enabled' if current.get('enabled') else 'disabled'})",
        default=current.get('enabled', False)
    )
    
    if enabled:
        # SMTP configuration
        console.print("\n[bold]SMTP Configuration:[/bold]")
        
        smtp_host = get_input("SMTP Host:", default=current.get('smtp_host', 'smtp.gmail.com'))
        if not smtp_host:
            smtp_host = current.get('smtp_host', 'smtp.gmail.com')
        
        smtp_port = get_input("SMTP Port:", default=str(current.get('smtp_port', 587)))
        try:
            smtp_port = int(smtp_port)
        except:
            smtp_port = 587
        
        smtp_username = get_input("SMTP Username:", default=current.get('smtp_username', ''))
        smtp_password = get_input("SMTP Password:", default=current.get('smtp_password', ''))
        from_email = get_input("From Email:", default=current.get('from_email', ''))
        
        # Recipients
        console.print("\n[bold]Recipients:[/bold]")
        current_emails = current.get('to_emails', [])
        if current_emails:
            console.print(f"Current: {', '.join(current_emails)}")
        
        to_emails_str = get_input("To Emails (comma-separated):", default=','.join(current_emails))
        to_emails = [e.strip() for e in to_emails_str.split(',') if e.strip()]
        
        # Save
        manager.config_manager.update_notification_settings(
            "email",
            enabled=True,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            from_email=from_email,
            to_emails=to_emails
        )
        print_success("Email notifications enabled")
    else:
        manager.config_manager.update_notification_settings("email", enabled=False)
        print_success("Email notifications disabled")


def configure_slack_notifications():
    """Configure Slack webhook notifications"""
    print_header()
    console.print("\n[bold cyan]═══ Slack Notifications ═══[/bold cyan]\n")
    
    current = manager.config_manager.get_notification_settings("slack")
    
    enabled = get_confirm(
        f"Enable Slack notifications? (currently: {'enabled' if current.get('enabled') else 'disabled'})",
        default=current.get('enabled', False)
    )
    
    if enabled:
        console.print("\n[bold]Webhook URL:[/bold]")
        console.print("[dim]Get webhook URL from: https://api.slack.com/messaging/webhooks[/dim]\n")
        
        webhook_url = get_input("Webhook URL:", default=current.get('webhook_url', ''))
        
        if not webhook_url:
            print_error("Webhook URL is required")
            return
        
        manager.config_manager.update_notification_settings(
            "slack",
            enabled=True,
            webhook_url=webhook_url
        )
        print_success("Slack notifications enabled")
    else:
        manager.config_manager.update_notification_settings("slack", enabled=False)
        print_success("Slack notifications disabled")


def configure_teams_notifications():
    """Configure Microsoft Teams webhook notifications"""
    print_header()
    console.print("\n[bold cyan]═══ Microsoft Teams Notifications ═══[/bold cyan]\n")
    
    current = manager.config_manager.get_notification_settings("teams")
    
    enabled = get_confirm(
        f"Enable Teams notifications? (currently: {'enabled' if current.get('enabled') else 'disabled'})",
        default=current.get('enabled', False)
    )
    
    if enabled:
        console.print("\n[bold]Webhook URL:[/bold]")
        console.print("[dim]Create incoming webhook in Teams channel settings[/dim]\n")
        
        webhook_url = get_input("Webhook URL:", default=current.get('webhook_url', ''))
        
        if not webhook_url:
            print_error("Webhook URL is required")
            return
        
        manager.config_manager.update_notification_settings(
            "teams",
            enabled=True,
            webhook_url=webhook_url
        )
        print_success("Teams notifications enabled")
    else:
        manager.config_manager.update_notification_settings("teams", enabled=False)
        print_success("Teams notifications disabled")


def configure_discord_notifications():
    """Configure Discord webhook notifications"""
    print_header()
    console.print("\n[bold cyan]═══ Discord Notifications ═══[/bold cyan]\n")
    
    current = manager.config_manager.get_notification_settings("discord")
    
    enabled = get_confirm(
        f"Enable Discord notifications? (currently: {'enabled' if current.get('enabled') else 'disabled'})",
        default=current.get('enabled', False)
    )
    
    if enabled:
        console.print("\n[bold]Webhook URL:[/bold]")
        console.print("[dim]Server Settings → Integrations → Webhooks[/dim]\n")
        
        webhook_url = get_input("Webhook URL:", default=current.get('webhook_url', ''))
        
        if not webhook_url:
            print_error("Webhook URL is required")
            return
        
        manager.config_manager.update_notification_settings(
            "discord",
            enabled=True,
            webhook_url=webhook_url
        )
        print_success("Discord notifications enabled")
    else:
        manager.config_manager.update_notification_settings("discord", enabled=False)
        print_success("Discord notifications disabled")


def test_notifications():
    """Send test notifications"""
    print_header()
    console.print("\n[bold cyan]═══ Test Notifications ═══[/bold cyan]\n")
    
    console.print("Sending test notifications to all enabled channels...\n")
    
    # Reload notification manager with current settings
    from core.notifications import NotificationManager, NotificationType
    notif_manager = NotificationManager(manager.config_manager.config)
    
    # Send test notification
    success = notif_manager.send(
        NotificationType.BACKUP_SUCCESS,
        "🧪 Test Notification",
        "This is a test notification from DBManager",
        database="test_database",
        backup_file="test_backup.dump",
        size_mb=12.34
    )
    
    if success:
        print_success("✅ Test notification sent successfully!")
        console.print("\nCheck your configured channels to verify receipt.")
    else:
        print_error("❌ No notifications were sent")
        console.print("\nEnsure at least one notification channel is enabled and configured.")
