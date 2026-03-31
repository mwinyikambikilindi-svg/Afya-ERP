from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetDepreciationLine(Base):
    __tablename__ = 'asset_depreciation_lines'

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('asset_depreciation_runs.id'), nullable=False)
    fixed_asset_id: Mapped[int] = mapped_column(ForeignKey('fixed_assets.id'), nullable=False)
    depreciation_amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False, default=Decimal('0.00'))
