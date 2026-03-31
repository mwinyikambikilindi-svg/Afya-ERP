from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetMaintenance(Base):
    __tablename__ = 'asset_maintenance'

    id: Mapped[int] = mapped_column(primary_key=True)
    fixed_asset_id: Mapped[int] = mapped_column(ForeignKey('fixed_assets.id'), nullable=False)
    maintenance_date: Mapped[date] = mapped_column(Date, nullable=False)
    maintenance_type: Mapped[str] = mapped_column(String(50), nullable=False)
    service_provider: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=Decimal('0.00'))
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
