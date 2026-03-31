from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FeeItem(Base):
    __tablename__ = "fee_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="TUITION")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # IPSAS-oriented configuration
    monetary_class: Mapped[str] = mapped_column(String(20), nullable=False, default="monetary")
    recognition_basis: Mapped[str] = mapped_column(String(30), nullable=False, default="over_time")
    is_refundable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # GL / GFS mapped accounts
    gl_receivable_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    gl_deferred_revenue_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    gl_revenue_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    gl_discount_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    gl_refund_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    gl_ecl_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)

    fee_structure_lines: Mapped[list["FeeStructureLine"]] = relationship("FeeStructureLine", back_populates="fee_item")

    def __repr__(self) -> str:
        return f"<FeeItem id={self.id} code={self.code!r} name={self.name!r}>"
