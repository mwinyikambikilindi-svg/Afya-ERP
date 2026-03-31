from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentWaiver(Base):
    __tablename__ = "student_waivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("student_invoices.id"), nullable=False)
    journal_batch_id: Mapped[int | None] = mapped_column(ForeignKey("journal_batches.id"), nullable=True)

    waiver_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    waiver_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    student: Mapped["Student"] = relationship("Student")
    invoice: Mapped["StudentInvoice"] = relationship("StudentInvoice")
