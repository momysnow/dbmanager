"""Notification settings menu"""

from typing import Any, Optional

from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from cli import console, manager
from utils.ui import (
    print_header,
    get_selection,
    get_input,
    get_confirm,
    print_success,
    print_error,
)


def _status_label(enabled: Optional[bool]) -> str:
    return "✅ Enabled" if enabled else "❌ Disabled"


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _configure_webhook(channel_key: str, title: str, help_text: str) -> None:
    print_header()
    console.print(f"\n[bold cyan]═══ {title} ═══[/bold cyan]\n")

    current = manager.config_manager.get_notification_settings(channel_key)
    enabled = get_confirm(
        (
            f"Enable {title.split(' Notifications')[0]} notifications? "
            f"(currently: {'enabled' if current.get('enabled') else 'disabled'})"
        ),
        default=current.get("enabled", False),
    )

    if enabled:
        console.print("\n[bold]Webhook URL:[/bold]")
        console.print(f"[dim]{help_text}[/dim]\n")

        webhook_url = get_input("Webhook URL:", default=current.get("webhook_url", ""))
        if not webhook_url:
            print_error("Webhook URL is required")
            return

        manager.config_manager.update_notification_settings(
            channel_key, enabled=True, webhook_url=webhook_url
        )
        print_success(f"{title} enabled")
    else:
        manager.config_manager.update_notification_settings(channel_key, enabled=False)
        print_success(f"{title} disabled")


def notification_menu() -> None:
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
        console.print(
            f"[bold]Email:[/bold] {_status_label(email_settings.get('enabled'))}"
        )
        console.print(
            f"[bold]Slack:[/bold] {_status_label(slack_settings.get('enabled'))}"
        )
        console.print(
            f"[bold]Teams:[/bold] {_status_label(teams_settings.get('enabled'))}"
        )
        console.print(
            f"[bold]Discord:[/bold] {_status_label(discord_settings.get('enabled'))}"
        )
        console.print()

        choices: list[Any] = [
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


def configure_email_notifications() -> None:
    """Configure email notification settings"""
    print_header()
    console.print("\n[bold cyan]═══ Email Notifications (SMTP) ═══[/bold cyan]\n")

    current = manager.config_manager.get_notification_settings("email")

    # Enable/Disable
    enabled = get_confirm(
        (
            "Enable email notifications? "
            f"(currently: {'enabled' if current.get('enabled') else 'disabled'})"
        ),
        default=current.get("enabled", False),
    )

    if enabled:
        # SMTP configuration
        console.print("\n[bold]SMTP Configuration:[/bold]")

        smtp_host = get_input(
            "SMTP Host:", default=current.get("smtp_host", "smtp.gmail.com")
        )
        if not smtp_host:
            smtp_host = current.get("smtp_host", "smtp.gmail.com")

        smtp_port = _parse_int(
            get_input("SMTP Port:", default=str(current.get("smtp_port", 587))), 587
        )

        smtp_username = get_input(
            "SMTP Username:", default=current.get("smtp_username", "")
        )
        smtp_password = get_input(
            "SMTP Password:", default=current.get("smtp_password", "")
        )
        from_email = get_input("From Email:", default=current.get("from_email", ""))

        # Recipients
        console.print("\n[bold]Recipients:[/bold]")
        current_emails = current.get("to_emails", [])
        if current_emails:
            console.print(f"Current: {', '.join(current_emails)}")

        to_emails_str = get_input(
            "To Emails (comma-separated):", default=",".join(current_emails)
        )
        to_emails = [e.strip() for e in to_emails_str.split(",") if e.strip()]

        # Save
        manager.config_manager.update_notification_settings(
            "email",
            enabled=True,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            from_email=from_email,
            to_emails=to_emails,
        )
        print_success("Email notifications enabled")
    else:
        manager.config_manager.update_notification_settings("email", enabled=False)
        print_success("Email notifications disabled")


def configure_slack_notifications() -> None:
    """Configure Slack webhook notifications"""
    _configure_webhook(
        "slack",
        "Slack Notifications",
        "Get webhook URL from: https://api.slack.com/messaging/webhooks",
    )


def configure_teams_notifications() -> None:
    """Configure Microsoft Teams webhook notifications"""
    _configure_webhook(
        "teams",
        "Microsoft Teams Notifications",
        "Create incoming webhook in Teams channel settings",
    )


def configure_discord_notifications() -> None:
    """Configure Discord webhook notifications"""
    _configure_webhook(
        "discord", "Discord Notifications", "Server Settings → Integrations → Webhooks"
    )


def test_notifications() -> None:
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
        size_mb=12.34,
    )

    if success:
        print_success("✅ Test notification sent successfully!")
        console.print("\nCheck your configured channels to verify receipt.")
    else:
        print_error("❌ No notifications were sent")
        console.print(
            "\nEnsure at least one notification channel is enabled and configured."
        )
