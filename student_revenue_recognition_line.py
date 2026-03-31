from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentRevenueRecognitionLine(Base):
    __tablename__ = "student_revenue_recognition_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("student_revenue_recognition_runs.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("student_invoices.id"), nullable=False)
    invoice_line_id: Mapped[int] = mapped_column(ForeignKey("student_invoice_lines.id"), nullable=False)
    fee_item_id: Mapped[int | None] = mapped_column(ForeignKey("fee_items.id"), nullable=True)
    deferred_gl_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    revenue_gl_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    service_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress_percent: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False, default=Decimal("0.0000"))
    recognized_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    run: Mapped["StudentRevenueRecognitionRun"] = relationship("StudentRevenueRecognitionRun", back_populates="lines")

    def __repr__(self) -> str:
        return f"<StudentRevenueRecognitionLine id={self.id} invoice_line_id={self.invoice_line_id} amount={self.recognized_amount}>"
