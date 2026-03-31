from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    journal_batch_id: Mapped[int] = mapped_column(ForeignKey("journal_batches.id"), nullable=False)
    gl_account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)

    journal_batch: Mapped["JournalBatch"] = relationship(
        "JournalBatch",
        back_populates="lines",
    )
