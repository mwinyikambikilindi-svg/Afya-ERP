from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NHIFRejection(Base):
    __tablename__ = "nhif_rejections"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("nhif_claim_batches.id"), nullable=False)
    loss_date: Mapped[date] = mapped_column(Date, nullable=False)
    rejected_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
