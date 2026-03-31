from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentRefund(Base):
    __tablename__ = "student_refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("student_payments.id"), nullable=True)
    cash_account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id"), nullable=False)
    refund_gl_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    journal_batch_id: Mapped[int | None] = mapped_column(ForeignKey("journal_batches.id"), nullable=True)

    refund_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    refund_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    student: Mapped["Student"] = relationship("Student")
    payment: Mapped["StudentPayment | None"] = relationship("StudentPayment")
