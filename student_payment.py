from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentPayment(Base):
    __tablename__ = "student_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    cash_account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id"), nullable=False)
    journal_batch_id: Mapped[int | None] = mapped_column(ForeignKey("journal_batches.id"), nullable=True)

    payment_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    unallocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")

    student: Mapped["Student"] = relationship("Student")
    allocations: Mapped[list["StudentPaymentAllocation"]] = relationship(
        "StudentPaymentAllocation",
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="StudentPaymentAllocation.id",
    )

    def __repr__(self) -> str:
        return f"<StudentPayment id={self.id} payment_no={self.payment_no!r} status={self.status!r}>"
