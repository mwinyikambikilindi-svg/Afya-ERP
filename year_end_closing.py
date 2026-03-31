from datetime import date
from sqlalchemy import String, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class YearEndClosing(Base):
    __tablename__ = "year_end_closings"

    id: Mapped[int] = mapped_column(primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    closing_date: Mapped[date] = mapped_column(Date, nullable=False)
    retained_surplus_account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id"), nullable=False)
    closing_journal_batch_id: Mapped[int] = mapped_column(ForeignKey("journal_batches.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted")
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)