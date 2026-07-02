"""PostSchedule model — scheduling rules for recurring / one-off social posts."""
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TenantScopedModel


class PostSchedule(TenantScopedModel):
    """A scheduling rule that creates SocialPost entries at defined times."""
    __tablename__ = 'post_schedule'

    account_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('social_account.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    author_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )

    # Name / label for this schedule rule
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Platform this schedule targets
    platform: Mapped[str] = mapped_column(String(30), nullable=False)

    # Content template (may include {{variable}} placeholders)
    content_template: Mapped[str] = mapped_column(Text, nullable=False)

    # one_off | daily | weekly | monthly
    recurrence: Mapped[str] = mapped_column(String(20), default='one_off', nullable=False)

    # ISO datetime for the next publish (or the single publish time for one_off)
    next_run_at: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Cron expression for recurring schedules (null for one_off)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=True)

    # Timezone string (e.g. 'Asia/Kolkata')
    timezone: Mapped[str] = mapped_column(String(60), default='UTC', nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Additional per-schedule meta (hashtags, media_ids, etc.)
    meta: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # active | paused | completed | failed
    status: Mapped[str] = mapped_column(String(20), default='active', nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'account_id': self.account_id,
            'author_id': self.author_id,
            'name': self.name,
            'platform': self.platform,
            'content_template': self.content_template,
            'recurrence': self.recurrence,
            'next_run_at': self.next_run_at,
            'cron_expression': self.cron_expression,
            'timezone': self.timezone,
            'is_active': self.is_active,
            'meta': self.meta,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
