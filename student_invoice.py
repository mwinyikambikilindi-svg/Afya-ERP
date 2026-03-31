from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentInvoice(Base):
    __tablename__ = "student_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    enrollment_id: Mapped[int | None] = mapped_column(ForeignKey("student_enrollments.id"), nullable=True)
    journal_batch_id: Mapped[int | None] = mapped_column(ForeignKey("journal_batches.id"), nullable=True)

    invoice_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False, default="TZS")
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")

    student: Mapped["Student"] = relationship("Student")
    enrollment: Mapped["StudentEnrollment | None"] = relationship("StudentEnrollment")
    lines: Mapped[list["StudentInvoiceLine"]] = relationship(
        "StudentInvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="StudentInvoiceLine.id",
    )
    allocations: Mapped[list["StudentPaymentAllocation"]] = relationship("StudentPaymentAllocation", back_populates="invoice")

    @property
    def is_posted(self) -> bool:
        return (self.status or "").lower() in {"posted", "partially_paid", "paid"}

    def __repr__(self) -> str:
        return f"<StudentInvoice id={self.id} invoice_no={self.invoice_no!r} status={self.status!r}>"
