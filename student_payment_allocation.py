from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentPaymentAllocation(Base):
    __tablename__ = "student_payment_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("student_payments.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("student_invoices.id"), nullable=False)
    invoice_line_id: Mapped[int] = mapped_column(ForeignKey("student_invoice_lines.id"), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    payment: Mapped["StudentPayment"] = relationship("StudentPayment", back_populates="allocations")
    invoice: Mapped["StudentInvoice"] = relationship("StudentInvoice", back_populates="allocations")
    invoice_line: Mapped["StudentInvoiceLine"] = relationship("StudentInvoiceLine", back_populates="allocations")

    def __repr__(self) -> str:
        return f"<StudentPaymentAllocation id={self.id} payment_id={self.payment_id} amount={self.allocated_amount}>"
