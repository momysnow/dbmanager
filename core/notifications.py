"""Notification system for backup events"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, cast
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import json


class NotificationType(Enum):
    """Notification event types"""

    BACKUP_SUCCESS = "backup_success"
    BACKUP_FAILURE = "backup_failure"
    RESTORE_SUCCESS = "restore_success"
    RESTORE_FAILURE = "restore_failure"
    SCHEDULE_SUCCESS = "schedule_success"
    SCHEDULE_FAILURE = "schedule_failure"


class BaseNotifier(ABC):
    """Base class for notification providers"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.enabled = config.get("enabled", False)

    @abstractmethod
    def send(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send a notification"""
        raise NotImplementedError

    def format_message(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> str:
        """Format message with additional context"""
        context = []

        if kwargs.get("database"):
            context.append(f"Database: {kwargs['database']}")

        if kwargs.get("backup_file"):
            context.append(f"File: {kwargs['backup_file']}")

        if kwargs.get("size_mb"):
            context.append(f"Size: {kwargs['size_mb']:.2f} MB")

        if kwargs.get("duration"):
            context.append(f"Duration: {kwargs['duration']}")

        if kwargs.get("error"):
            context.append(f"Error: {kwargs['error']}")

        full_message = f"{title}\n\n{message}"
        if context:
            full_message += "\n\n" + "\n".join(context)

        return full_message


class EmailNotifier(BaseNotifier):
    """Email notifications via SMTP"""

    def send(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send email notification"""
        if not self.enabled:
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = str(self.config.get("from_email") or "")
            to_emails = list(self.config.get("to_emails", []))
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = f"DBManager: {title}"

            # Format body
            body = self.format_message(notification_type, title, message, **kwargs)
            msg.attach(MIMEText(body, "plain"))

            # Send email
            smtp_host = str(self.config.get("smtp_host") or "")
            smtp_port = int(self.config.get("smtp_port", 587) or 587)
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()

                username = self.config.get("smtp_username")
                password = self.config.get("smtp_password")

                if username and password:
                    server.login(username, password)

                server.send_message(msg)

            return True
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False


class SlackNotifier(BaseNotifier):
    """Slack notifications via webhook"""

    def send(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send Slack notification"""
        if not self.enabled:
            return False

        try:
            # Determine color based on type
            color = "#36a64f"  # green
            if "failure" in notification_type.value:
                color = "#ff0000"  # red

            # Build Slack message
            payload: Dict[str, Any] = {
                "attachments": [
                    {"color": color, "title": title, "text": message, "fields": []}
                ]
            }
            attachments = cast(List[Dict[str, Any]], payload["attachments"])
            fields = cast(List[Dict[str, Any]], attachments[0]["fields"])

            # Add fields
            if kwargs.get("database"):
                fields.append(
                    {"title": "Database", "value": kwargs["database"], "short": True}
                )

            if kwargs.get("backup_file"):
                fields.append(
                    {
                        "title": "Backup File",
                        "value": kwargs["backup_file"],
                        "short": False,
                    }
                )

            if kwargs.get("size_mb"):
                fields.append(
                    {
                        "title": "Size",
                        "value": f"{kwargs['size_mb']:.2f} MB",
                        "short": True,
                    }
                )

            if kwargs.get("error"):
                fields.append(
                    {"title": "Error", "value": kwargs["error"], "short": False}
                )

            webhook_url = self.config.get("webhook_url")
            if not isinstance(webhook_url, str) or not webhook_url:
                raise ValueError("Slack webhook URL not configured")

            # Send to webhook
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

            return response.status_code == 200
        except Exception as e:
            print(f"Slack notification failed: {e}")
            return False


class TeamsNotifier(BaseNotifier):
    """Microsoft Teams notifications via webhook"""

    def send(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send Teams notification"""
        if not self.enabled:
            return False

        try:
            # Determine theme color
            theme_color = "28a745"  # green
            if "failure" in notification_type.value:
                theme_color = "dc3545"  # red

            # Build Teams message (Adaptive Card format)
            payload: Dict[str, Any] = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "themeColor": theme_color,
                "title": title,
                "text": message,
                "sections": [{"facts": []}],
            }
            sections = cast(List[Dict[str, Any]], payload["sections"])
            facts = cast(List[Dict[str, Any]], sections[0]["facts"])

            # Add facts
            if kwargs.get("database"):
                facts.append({"name": "Database", "value": kwargs["database"]})

            if kwargs.get("backup_file"):
                facts.append({"name": "Backup File", "value": kwargs["backup_file"]})

            if kwargs.get("size_mb"):
                facts.append({"name": "Size", "value": f"{kwargs['size_mb']:.2f} MB"})

            if kwargs.get("error"):
                facts.append({"name": "Error", "value": kwargs["error"]})

            webhook_url = self.config.get("webhook_url")
            if not isinstance(webhook_url, str) or not webhook_url:
                raise ValueError("Teams webhook URL not configured")

            # Send to webhook
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

            return response.status_code == 200
        except Exception as e:
            print(f"Teams notification failed: {e}")
            return False


class DiscordNotifier(BaseNotifier):
    """Discord notifications via webhook"""

    def send(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send Discord notification"""
        if not self.enabled:
            return False

        try:
            # Determine color
            color = 3066993  # green
            if "failure" in notification_type.value:
                color = 15158332  # red

            # Build Discord embed
            embed: Dict[str, Any] = {
                "title": title,
                "description": message,
                "color": color,
                "fields": [],
            }
            fields = cast(List[Dict[str, Any]], embed["fields"])

            # Add fields
            if kwargs.get("database"):
                fields.append(
                    {"name": "Database", "value": kwargs["database"], "inline": True}
                )

            if kwargs.get("backup_file"):
                fields.append(
                    {
                        "name": "Backup File",
                        "value": kwargs["backup_file"],
                        "inline": False,
                    }
                )

            if kwargs.get("size_mb"):
                fields.append(
                    {
                        "name": "Size",
                        "value": f"{kwargs['size_mb']:.2f} MB",
                        "inline": True,
                    }
                )

            if kwargs.get("error"):
                fields.append(
                    {"name": "Error", "value": kwargs["error"], "inline": False}
                )

            payload = {"embeds": [embed]}

            webhook_url = self.config.get("webhook_url")
            if not isinstance(webhook_url, str) or not webhook_url:
                raise ValueError("Discord webhook URL not configured")

            # Send to webhook
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

            return response.status_code in [200, 204]
        except Exception as e:
            print(f"Discord notification failed: {e}")
            return False


class NotificationManager:
    """Manages all notification providers"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.notifiers: List[BaseNotifier] = []

        # Initialize notifiers from config
        notifications_config = config.get("notifications", {})

        if "email" in notifications_config:
            self.notifiers.append(EmailNotifier(notifications_config["email"]))

        if "slack" in notifications_config:
            self.notifiers.append(SlackNotifier(notifications_config["slack"]))

        if "teams" in notifications_config:
            self.notifiers.append(TeamsNotifier(notifications_config["teams"]))

        if "discord" in notifications_config:
            self.notifiers.append(DiscordNotifier(notifications_config["discord"]))

    def send(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send notification to all enabled providers"""
        results = []

        for notifier in self.notifiers:
            if notifier.enabled:
                try:
                    result = notifier.send(notification_type, title, message, **kwargs)
                    results.append(result)
                except Exception as e:
                    print(f"Notification error ({notifier.__class__.__name__}): {e}")
                    results.append(False)

        return any(results) if results else False

    def send_backup_success(
        self,
        database: str,
        backup_file: str,
        size_mb: float,
        duration: Optional[str] = None,
    ) -> bool:
        """Send backup success notification"""
        return self.send(
            NotificationType.BACKUP_SUCCESS,
            "✅ Backup Successful",
            "Database backup completed successfully",
            database=database,
            backup_file=backup_file,
            size_mb=size_mb,
            duration=duration,
        )

    def send_backup_failure(self, database: str, error: str) -> bool:
        """Send backup failure notification"""
        return self.send(
            NotificationType.BACKUP_FAILURE,
            "❌ Backup Failed",
            "Database backup failed",
            database=database,
            error=error,
        )

    def send_restore_success(self, database: str, backup_file: str) -> bool:
        """Send restore success notification"""
        return self.send(
            NotificationType.RESTORE_SUCCESS,
            "✅ Restore Successful",
            "Database restore completed successfully",
            database=database,
            backup_file=backup_file,
        )

    def send_restore_failure(self, database: str, backup_file: str, error: str) -> bool:
        """Send restore failure notification"""
        return self.send(
            NotificationType.RESTORE_FAILURE,
            "❌ Restore Failed",
            "Database restore failed",
            database=database,
            backup_file=backup_file,
            error=error,
        )
