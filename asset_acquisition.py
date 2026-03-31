from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetAcquisition(Base):
    __tablename__ = 'asset_acquisitions'

    id: Mapped[int] = mapped_column(primary_key=True)
    fixed_asset_id: Mapped[int] = mapped_column(ForeignKey('fixed_assets.id'), nullable=False)
    acquisition_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey('suppliers.id'), nullable=True)
    payment_account_id: Mapped[int | None] = mapped_column(ForeignKey('gl_accounts.id'), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=Decimal('0.00'))
    reference_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    journal_batch_id: Mapped[int | None] = mapped_column(ForeignKey('journal_batches.id'), nullable=True)
