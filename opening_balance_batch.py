from datetime import date
from sqlalchemy import String, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class OpeningBalanceBatch(Base):
    __tablename__ = "opening_balance_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    opening_date: Mapped[date] = mapped_column(Date, nullable=False)
    journal_batch_id: Mapped[int] = mapped_column(ForeignKey("journal_batches.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted")
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)