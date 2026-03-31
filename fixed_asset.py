from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixedAsset(Base):
    __tablename__ = 'fixed_assets'

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    asset_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey('asset_categories.id'), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey('branches.id'), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey('asset_locations.id'), nullable=True)
    custodian_id: Mapped[int | None] = mapped_column(ForeignKey('asset_custodians.id'), nullable=True)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False)
    capitalization_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=Decimal('0.00'))
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=Decimal('0.00'))
    useful_life_months: Mapped[int] = mapped_column(nullable=False, default=60)
    depreciation_method: Mapped[str] = mapped_column(String(30), nullable=False, default='STRAIGHT_LINE')
    accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=Decimal('0.00'))
    carrying_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=Decimal('0.00'))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='active')
    funding_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
