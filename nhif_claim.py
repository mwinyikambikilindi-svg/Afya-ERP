from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NHIFClaim(Base):
    __tablename__ = "nhif_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("nhif_claim_batches.id"), nullable=False)
    patient_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    service_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    approved_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    adjusted_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    rejected_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    adjudication_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    adjudication_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
