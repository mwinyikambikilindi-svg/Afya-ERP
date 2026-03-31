from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    period_no: Mapped[int] = mapped_column(nullable=False)
    period_name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    fiscal_year: Mapped["FiscalYear"] = relationship("FiscalYear", back_populates="periods")
    journal_batches: Mapped[list["JournalBatch"]] = relationship(
        "JournalBatch",
        back_populates="period",
    )

    def contains_date(self, target_date: date) -> bool:
        return self.start_date <= target_date <= self.end_date

    @property
    def is_open(self) -> bool:
        return (self.status or "").lower() == "open"
