"""Notification settings Pydantic models"""

from pydantic import BaseModel, Field
from typing import List, Optional


class EmailNotificationSettings(BaseModel):
    enabled: bool = Field(default=False, description="Enable email notifications")
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_username: str = Field(default="", description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    from_email: str = Field(default="", description="From email")
    to_emails: List[str] = Field(default_factory=list, description="Recipient emails")


class EmailNotificationSettingsResponse(BaseModel):
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    from_email: str
    to_emails: List[str]
    smtp_password_set: bool


class WebhookNotificationSettings(BaseModel):
    enabled: bool = Field(default=False, description="Enable webhook notifications")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL")


class WebhookNotificationSettingsResponse(BaseModel):
    enabled: bool
    webhook_url_set: bool


class NotificationsResponse(BaseModel):
    email: EmailNotificationSettingsResponse
    slack: WebhookNotificationSettingsResponse
    teams: WebhookNotificationSettingsResponse
    discord: WebhookNotificationSettingsResponse


class NotificationTestResponse(BaseModel):
    success: bool
    message: str
