from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetDepreciationRun(Base):
    __tablename__ = 'asset_depreciation_runs'

    id: Mapped[int] = mapped_column(primary_key=True)
    run_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_label: Mapped[str] = mapped_column(String(30), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    journal_batch_id: Mapped[int | None] = mapped_column(ForeignKey('journal_batches.id'), nullable=True)
