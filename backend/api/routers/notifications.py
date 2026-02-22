"""Notification settings endpoints"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from api.models.notifications import (
    EmailNotificationSettings,
    EmailNotificationSettingsResponse,
    WebhookNotificationSettings,
    WebhookNotificationSettingsResponse,
    NotificationsResponse,
    NotificationTestResponse,
)
from api.dependencies import get_config_manager, get_db_manager
from config import ConfigManager
from core.manager import DBManager
from core.notifications import NotificationManager, NotificationType

router = APIRouter()


def _email_response(settings: Dict[str, Any]) -> EmailNotificationSettingsResponse:
    return EmailNotificationSettingsResponse(
        enabled=settings.get("enabled", False),
        smtp_host=settings.get("smtp_host", ""),
        smtp_port=int(settings.get("smtp_port", 587)),
        smtp_username=settings.get("smtp_username", ""),
        from_email=settings.get("from_email", ""),
        to_emails=settings.get("to_emails", []) or [],
        smtp_password_set=bool(settings.get("smtp_password")),
    )


def _webhook_response(settings: Dict[str, Any]) -> WebhookNotificationSettingsResponse:
    return WebhookNotificationSettingsResponse(
        enabled=settings.get("enabled", False),
        webhook_url_set=bool(settings.get("webhook_url")),
    )


@router.get("/notifications", response_model=NotificationsResponse)
async def get_notifications(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> NotificationsResponse:
    """Get notification settings (secrets excluded)"""
    notifications = config_manager.get_notification_settings()

    return NotificationsResponse(
        email=_email_response(notifications.get("email", {})),
        slack=_webhook_response(notifications.get("slack", {})),
        teams=_webhook_response(notifications.get("teams", {})),
        discord=_webhook_response(notifications.get("discord", {})),
    )


@router.get("/notifications/email", response_model=EmailNotificationSettingsResponse)
async def get_email_notifications(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> EmailNotificationSettingsResponse:
    """Get email notification settings"""
    return _email_response(config_manager.get_notification_settings("email"))


@router.put("/notifications/email", response_model=EmailNotificationSettingsResponse)
async def update_email_notifications(
    settings: EmailNotificationSettings,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> EmailNotificationSettingsResponse:
    """Update email notification settings"""
    current = config_manager.get_notification_settings("email")

    update_data = settings.model_dump()
    if update_data.get("smtp_password") in (None, "") and current.get("smtp_password"):
        update_data.pop("smtp_password", None)

    config_manager.update_notification_settings("email", **update_data)

    updated = config_manager.get_notification_settings("email")
    return _email_response(updated)


@router.get(
    "/notifications/{provider}", response_model=WebhookNotificationSettingsResponse
)
async def get_webhook_notifications(
    provider: str, config_manager: ConfigManager = Depends(get_config_manager)
) -> WebhookNotificationSettingsResponse:
    """Get webhook notification settings for provider"""
    if provider not in {"slack", "teams", "discord"}:
        raise HTTPException(status_code=400, detail="Invalid provider")

    return _webhook_response(config_manager.get_notification_settings(provider))


@router.put(
    "/notifications/{provider}", response_model=WebhookNotificationSettingsResponse
)
async def update_webhook_notifications(
    provider: str,
    settings: WebhookNotificationSettings,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> WebhookNotificationSettingsResponse:
    """Update webhook notification settings for provider"""
    if provider not in {"slack", "teams", "discord"}:
        raise HTTPException(status_code=400, detail="Invalid provider")

    current = config_manager.get_notification_settings(provider)
    update_data = settings.model_dump()
    if update_data.get("webhook_url") in (None, "") and current.get("webhook_url"):
        update_data.pop("webhook_url", None)

    config_manager.update_notification_settings(provider, **update_data)
    updated = config_manager.get_notification_settings(provider)
    return _webhook_response(updated)


@router.post("/notifications/test", response_model=NotificationTestResponse)
async def test_notifications(
    db_manager: DBManager = Depends(get_db_manager),
) -> NotificationTestResponse:
    """Send test notification to all enabled channels"""
    notif_manager = NotificationManager(db_manager.config_manager.config)
    success = notif_manager.send(
        NotificationType.BACKUP_SUCCESS,
        "🧪 Test Notification",
        "This is a test notification from DBManager",
        database="test_database",
        backup_file="test_backup.dump",
        size_mb=12.34,
    )

    if success:
        return NotificationTestResponse(success=True, message="Test notification sent")

    return NotificationTestResponse(success=False, message="No notifications were sent")
