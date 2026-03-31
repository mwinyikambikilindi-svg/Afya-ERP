from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FiscalYear(Base):
    __tablename__ = "fiscal_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    year_name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    periods: Mapped[list["AccountingPeriod"]] = relationship(
        "AccountingPeriod",
        back_populates="fiscal_year",
        order_by="AccountingPeriod.start_date",
    )

    def contains_date(self, target_date: date) -> bool:
        return self.start_date <= target_date <= self.end_date

    @property
    def is_open(self) -> bool:
        return (self.status or "").lower() == "open"
