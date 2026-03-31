from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentRevenueRecognitionRun(Base):
    __tablename__ = "student_revenue_recognition_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_recognized_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    journal_batch_id: Mapped[int | None] = mapped_column(ForeignKey("journal_batches.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    lines: Mapped[list["StudentRevenueRecognitionLine"]] = relationship(
        "StudentRevenueRecognitionLine",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="StudentRevenueRecognitionLine.id",
    )

    def __repr__(self) -> str:
        return f"<StudentRevenueRecognitionRun id={self.id} run_no={self.run_no!r} status={self.status!r}>"
