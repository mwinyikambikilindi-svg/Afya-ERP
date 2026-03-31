from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FeeStructureLine(Base):
    __tablename__ = "fee_structure_lines"
    __table_args__ = (
        UniqueConstraint("fee_structure_id", "fee_item_id", name="uq_fee_structure_line_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fee_structure_id: Mapped[int] = mapped_column(ForeignKey("fee_structures.id"), nullable=False)
    fee_item_id: Mapped[int] = mapped_column(ForeignKey("fee_items.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=1)

    fee_structure: Mapped["FeeStructure"] = relationship("FeeStructure", back_populates="lines")
    fee_item: Mapped["FeeItem"] = relationship("FeeItem", back_populates="fee_structure_lines")

    def __repr__(self) -> str:
        return f"<FeeStructureLine id={self.id} fee_structure_id={self.fee_structure_id} fee_item_id={self.fee_item_id}>"
