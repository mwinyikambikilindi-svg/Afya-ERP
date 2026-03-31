from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NHIFClaimBatch(Base):
    __tablename__ = "nhif_claim_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    facility_name: Mapped[str] = mapped_column(String(200), nullable=False)
    claim_month: Mapped[str] = mapped_column(String(20), nullable=False)
    claim_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    submission_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
