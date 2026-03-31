from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentInvoiceLine(Base):
    __tablename__ = "student_invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("student_invoices.id"), nullable=False)
    fee_item_id: Mapped[int | None] = mapped_column(ForeignKey("fee_items.id"), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    receivable_gl_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    recognition_gl_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    recognition_basis: Mapped[str] = mapped_column(String(30), nullable=False, default="over_time")
    monetary_class: Mapped[str] = mapped_column(String(20), nullable=False, default="monetary")

    invoice: Mapped["StudentInvoice"] = relationship("StudentInvoice", back_populates="lines")
    fee_item: Mapped["FeeItem | None"] = relationship("FeeItem")
    allocations: Mapped[list["StudentPaymentAllocation"]] = relationship("StudentPaymentAllocation", back_populates="invoice_line")

    def __repr__(self) -> str:
        return f"<StudentInvoiceLine id={self.id} invoice_id={self.invoice_id} amount={self.amount}>"
