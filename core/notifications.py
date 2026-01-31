"""Notification system for backup events"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
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
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
    
    @abstractmethod
    def send(self, notification_type: NotificationType, title: str, message: str, **kwargs):
        """Send a notification"""
        pass
    
    def format_message(self, notification_type: NotificationType, title: str, message: str, **kwargs) -> str:
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
    
    def send(self, notification_type: NotificationType, title: str, message: str, **kwargs):
        """Send email notification"""
        if not self.enabled:
            return
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.get('from_email')
            msg['To'] = ', '.join(self.config.get('to_emails', []))
            msg['Subject'] = f"DBManager: {title}"
            
            # Format body
            body = self.format_message(notification_type, title, message, **kwargs)
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.config.get('smtp_host'), self.config.get('smtp_port', 587)) as server:
                server.starttls()
                
                username = self.config.get('smtp_username')
                password = self.config.get('smtp_password')
                
                if username and password:
                    server.login(username, password)
                
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False


class SlackNotifier(BaseNotifier):
    """Slack notifications via webhook"""
    
    def send(self, notification_type: NotificationType, title: str, message: str, **kwargs):
        """Send Slack notification"""
        if not self.enabled:
            return
        
        try:
            # Determine color based on type
            color = "#36a64f"  # green
            if "failure" in notification_type.value:
                color = "#ff0000"  # red
            
            # Build Slack message
            payload = {
                "attachments": [{
                    "color": color,
                    "title": title,
                    "text": message,
                    "fields": []
                }]
            }
            
            # Add fields
            if kwargs.get("database"):
                payload["attachments"][0]["fields"].append({
                    "title": "Database",
                    "value": kwargs["database"],
                    "short": True
                })
            
            if kwargs.get("backup_file"):
                payload["attachments"][0]["fields"].append({
                    "title": "Backup File",
                    "value": kwargs["backup_file"],
                    "short": False
                })
            
            if kwargs.get("size_mb"):
                payload["attachments"][0]["fields"].append({
                    "title": "Size",
                    "value": f"{kwargs['size_mb']:.2f} MB",
                    "short": True
                })
            
            if kwargs.get("error"):
                payload["attachments"][0]["fields"].append({
                    "title": "Error",
                    "value": kwargs["error"],
                    "short": False
                })
            
            # Send to webhook
            response = requests.post(
                self.config.get('webhook_url'),
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Slack notification failed: {e}")
            return False


class TeamsNotifier(BaseNotifier):
    """Microsoft Teams notifications via webhook"""
    
    def send(self, notification_type: NotificationType, title: str, message: str, **kwargs):
        """Send Teams notification"""
        if not self.enabled:
            return
        
        try:
            # Determine theme color
            theme_color = "28a745"  # green
            if "failure" in notification_type.value:
                theme_color = "dc3545"  # red
            
            # Build Teams message (Adaptive Card format)
            payload = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "themeColor": theme_color,
                "title": title,
                "text": message,
                "sections": [{
                    "facts": []
                }]
            }
            
            # Add facts
            if kwargs.get("database"):
                payload["sections"][0]["facts"].append({
                    "name": "Database",
                    "value": kwargs["database"]
                })
            
            if kwargs.get("backup_file"):
                payload["sections"][0]["facts"].append({
                    "name": "Backup File",
                    "value": kwargs["backup_file"]
                })
            
            if kwargs.get("size_mb"):
                payload["sections"][0]["facts"].append({
                    "name": "Size",
                    "value": f"{kwargs['size_mb']:.2f} MB"
                })
            
            if kwargs.get("error"):
                payload["sections"][0]["facts"].append({
                    "name": "Error",
                    "value": kwargs["error"]
                })
            
            # Send to webhook
            response = requests.post(
                self.config.get('webhook_url'),
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Teams notification failed: {e}")
            return False


class DiscordNotifier(BaseNotifier):
    """Discord notifications via webhook"""
    
    def send(self, notification_type: NotificationType, title: str, message: str, **kwargs):
        """Send Discord notification"""
        if not self.enabled:
            return
        
        try:
            # Determine color
            color = 3066993  # green
            if "failure" in notification_type.value:
                color = 15158332  # red
            
            # Build Discord embed
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "fields": []
            }
            
            # Add fields
            if kwargs.get("database"):
                embed["fields"].append({
                    "name": "Database",
                    "value": kwargs["database"],
                    "inline": True
                })
            
            if kwargs.get("backup_file"):
                embed["fields"].append({
                    "name": "Backup File",
                    "value": kwargs["backup_file"],
                    "inline": False
                })
            
            if kwargs.get("size_mb"):
                embed["fields"].append({
                    "name": "Size",
                    "value": f"{kwargs['size_mb']:.2f} MB",
                    "inline": True
                })
            
            if kwargs.get("error"):
                embed["fields"].append({
                    "name": "Error",
                    "value": kwargs["error"],
                    "inline": False
                })
            
            payload = {
                "embeds": [embed]
            }
            
            # Send to webhook
            response = requests.post(
                self.config.get('webhook_url'),
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"Discord notification failed: {e}")
            return False


class NotificationManager:
    """Manages all notification providers"""
    
    def __init__(self, config: Dict[str, Any]):
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
    
    def send(self, notification_type: NotificationType, title: str, message: str, **kwargs):
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
    
    def send_backup_success(self, database: str, backup_file: str, size_mb: float, duration: str = None):
        """Send backup success notification"""
        return self.send(
            NotificationType.BACKUP_SUCCESS,
            "✅ Backup Successful",
            f"Database backup completed successfully",
            database=database,
            backup_file=backup_file,
            size_mb=size_mb,
            duration=duration
        )
    
    def send_backup_failure(self, database: str, error: str):
        """Send backup failure notification"""
        return self.send(
            NotificationType.BACKUP_FAILURE,
            "❌ Backup Failed",
            f"Database backup failed",
            database=database,
            error=error
        )
    
    def send_restore_success(self, database: str, backup_file: str):
        """Send restore success notification"""
        return self.send(
            NotificationType.RESTORE_SUCCESS,
            "✅ Restore Successful",
            f"Database restore completed successfully",
            database=database,
            backup_file=backup_file
        )
    
    def send_restore_failure(self, database: str, backup_file: str, error: str):
        """Send restore failure notification"""
        return self.send(
            NotificationType.RESTORE_FAILURE,
            "❌ Restore Failed",
            f"Database restore failed",
            database=database,
            backup_file=backup_file,
            error=error
        )
