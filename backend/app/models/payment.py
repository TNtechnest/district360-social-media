"""Payment models — transactions, plans, invoices, refunds."""

from sqlalchemy import String, Text, Integer, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class SubscriptionPlan(TenantScopedModel):
    """A billable subscription plan."""
    __tablename__ = 'subscription_plan'

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default='INR', nullable=False)
    interval: Mapped[str] = mapped_column(String(20), default='monthly', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    features: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, nullable=True)
    max_storage_gb: Mapped[int] = mapped_column(Integer, nullable=True)
    provider_plan_id: Mapped[str] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('district_id', 'code', name='uix_plan_district_code'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'amount': self.amount,
            'currency': self.currency,
            'interval': self.interval,
            'is_active': self.is_active,
            'features': self.features,
            'max_users': self.max_users,
            'max_storage_gb': self.max_storage_gb,
            'provider_plan_id': self.provider_plan_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PaymentTransaction(TenantScopedModel):
    """A payment transaction record."""
    __tablename__ = 'payment_transaction'

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('subscription_plan.id', ondelete='SET NULL'), nullable=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True,
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_order_id: Mapped[str] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default='INR', nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    invoice_url: Mapped[str] = mapped_column(Text, nullable=True)
    refund_status: Mapped[str] = mapped_column(String(20), nullable=True)
    refund_amount: Mapped[float] = mapped_column(Float, nullable=True)
    refund_reason: Mapped[str] = mapped_column(Text, nullable=True)
    refunded_at: Mapped[str] = mapped_column(String(50), nullable=True)
    paid_at: Mapped[str] = mapped_column(String(50), nullable=True)
    webhook_data: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    plan = relationship('SubscriptionPlan', foreign_keys=[plan_id])
    user = relationship('User', foreign_keys=[user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'plan_id': self.plan_id,
            'user_id': self.user_id,
            'provider': self.provider,
            'transaction_id': self.transaction_id,
            'provider_order_id': self.provider_order_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'payment_method': self.payment_method,
            'description': self.description,
            'invoice_url': self.invoice_url,
            'refund_status': self.refund_status,
            'refund_amount': self.refund_amount,
            'refund_reason': self.refund_reason,
            'refunded_at': self.refunded_at,
            'paid_at': self.paid_at,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
