"""Notification models — templates and delivery records."""
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TenantScopedModel


class NotificationTemplate(TenantScopedModel):
    """Tenant-configurable message template for a platform channel."""
    __tablename__ = 'notification_template'

    # Event key that triggers this template (e.g. 'complaint.created')
    event_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # email | sms | whatsapp | push
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    subject: Mapped[str] = mapped_column(String(255), nullable=True)   # email only
    body: Mapped[str] = mapped_column(Text, nullable=False)             # Jinja2-style template
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('district_id', 'event_key', 'channel',
                            name='uix_notif_template_district_event_channel'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'event_key': self.event_key,
            'channel': self.channel,
            'subject': self.subject,
            'body': self.body,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Notification(TenantScopedModel):
    """A single notification delivery record."""
    __tablename__ = 'notification'

    user_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    template_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('notification_template.id', ondelete='SET NULL'),
        nullable=True,
    )

    # email | sms | whatsapp | push
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Recipient address (email addr, phone number, device token)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)

    subject: Mapped[str] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # pending | sent | failed | bounced
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False, index=True)

    # Event that triggered this notification
    event_key: Mapped[str] = mapped_column(String(100), nullable=True)

    # Provider response / message ID
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    sent_at: Mapped[str] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'user_id': self.user_id,
            'channel': self.channel,
            'recipient': self.recipient,
            'subject': self.subject,
            'body': self.body,
            'status': self.status,
            'event_key': self.event_key,
            'provider_message_id': self.provider_message_id,
            'error_message': self.error_message,
            'sent_at': self.sent_at,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
