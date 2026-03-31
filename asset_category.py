from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetCategory(Base):
    __tablename__ = 'asset_categories'

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    depreciation_method: Mapped[str] = mapped_column(String(30), default='STRAIGHT_LINE', nullable=False)
    useful_life_months: Mapped[int] = mapped_column(nullable=False, default=60)
    gl_asset_account_id: Mapped[int | None] = mapped_column(ForeignKey('gl_accounts.id'), nullable=True)
    gl_accumulated_depreciation_account_id: Mapped[int | None] = mapped_column(ForeignKey('gl_accounts.id'), nullable=True)
    gl_depreciation_expense_account_id: Mapped[int | None] = mapped_column(ForeignKey('gl_accounts.id'), nullable=True)
    gl_disposal_gain_account_id: Mapped[int | None] = mapped_column(ForeignKey('gl_accounts.id'), nullable=True)
    gl_disposal_loss_account_id: Mapped[int | None] = mapped_column(ForeignKey('gl_accounts.id'), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
