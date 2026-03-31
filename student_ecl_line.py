from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentECLLine(Base):
    __tablename__ = "student_ecl_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("student_ecl_runs.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("student_invoices.id"), nullable=False)
    invoice_line_id: Mapped[int] = mapped_column(ForeignKey("student_invoice_lines.id"), nullable=False)
    ecl_expense_gl_account_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)
    age_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    loss_rate: Mapped[Decimal] = mapped_column(Numeric(9, 4), nullable=False, default=Decimal("0.0000"))
    expected_loss_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    run: Mapped["StudentECLRun"] = relationship("StudentECLRun", back_populates="lines")
