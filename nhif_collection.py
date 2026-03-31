from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NHIFCollection(Base):
    __tablename__ = "nhif_collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("nhif_claim_batches.id"), nullable=False)
    receipt_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    bank_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    remittance_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
