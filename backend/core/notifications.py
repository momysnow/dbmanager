"""Notification system for backup events"""

import ipaddress
import json
import logging
import os
import socket
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)


def _is_private_or_local_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # Refuse unparseable hosts.
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _assert_safe_webhook_url(url: str) -> None:
    """Refuse webhook URLs that resolve to internal/loopback/link-local IPs.

    Mitigates SSRF: an admin who can configure a webhook URL must not be able
    to make the API call internal services (cloud metadata, k8s API, etc.).
    Set DBMANAGER_ALLOW_INTERNAL_WEBHOOKS=1 to bypass for trusted dev setups.
    """
    if os.getenv("DBMANAGER_ALLOW_INTERNAL_WEBHOOKS", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError(f"Invalid webhook URL: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Webhook URL must be http(s), got {parsed.scheme!r}")

    host = parsed.hostname
    if not host:
        raise ValueError("Webhook URL missing host")

    # Resolve and check every address (DNS rebinding-resistant).
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"Webhook host {host!r} did not resolve: {exc}") from exc

    for info in infos:
        ip = info[4][0]
        if _is_private_or_local_ip(ip):
            raise ValueError(
                f"Webhook URL host {host!r} resolves to a non-public IP "
                f"({ip}); refused for SSRF protection."
            )


class NotificationType(Enum):
    """Notification event types"""

    BACKUP_SUCCESS = "backup_success"
    BACKUP_FAILURE = "backup_failure"
    RESTORE_SUCCESS = "restore_success"
    RESTORE_FAILURE = "restore_failure"
    SCHEDULE_SUCCESS = "schedule_success"
    SCHEDULE_FAILURE = "schedule_failure"
    DB_DOWN = "db_down"
    DB_UP = "db_up"


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
            logger.info(f"Email notification failed: {e}")
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
            if (
                "failure" in notification_type.value
                or "down" in notification_type.value
            ):
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
            _assert_safe_webhook_url(webhook_url)

            # Send to webhook
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            return response.status_code == 200
        except Exception as e:
            logger.warning("Slack notification failed: %s", e)
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
            if (
                "failure" in notification_type.value
                or "down" in notification_type.value
            ):
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
            _assert_safe_webhook_url(webhook_url)

            # Send to webhook
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            return response.status_code == 200
        except Exception as e:
            logger.warning("Teams notification failed: %s", e)
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
            if (
                "failure" in notification_type.value
                or "down" in notification_type.value
            ):
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
            _assert_safe_webhook_url(webhook_url)

            # Send to webhook
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            return response.status_code in [200, 204]
        except Exception as e:
            logger.info(f"Discord notification failed: {e}")
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
                    logger.info(f"Notification error ({notifier.__class__.__name__}): {e}")
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

    def send_db_down(self, database: str) -> bool:
        """Send database down notification"""
        return self.send(
            NotificationType.DB_DOWN,
            "🔴 Database Unreachable",
            f"Database '{database}' is not responding to ping checks",
            database=database,
        )

    def send_db_up(self, database: str) -> bool:
        """Send database recovered notification"""
        return self.send(
            NotificationType.DB_UP,
            "🟢 Database Recovered",
            f"Database '{database}' is back online",
            database=database,
        )
