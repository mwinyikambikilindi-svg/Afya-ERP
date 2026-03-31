from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JournalBatch(Base):
    __tablename__ = "journal_batches"

    STATUS_DRAFT = "draft"
    STATUS_PENDING_APPROVAL = "pending_approval"
    STATUS_POSTED = "posted"
    STATUS_REJECTED = "rejected"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    period_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_periods.id"), nullable=True)

    batch_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    journal_date: Mapped[date] = mapped_column(Date, nullable=False)

    source_module: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT)

    period: Mapped["AccountingPeriod | None"] = relationship(
        "AccountingPeriod",
        back_populates="journal_batches",
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="journal_batch",
        cascade="all, delete-orphan",
    )

    @property
    def is_draft(self) -> bool:
        return (self.status or "").lower() == self.STATUS_DRAFT

    @property
    def is_pending_approval(self) -> bool:
        return (self.status or "").lower() == self.STATUS_PENDING_APPROVAL

    @property
    def is_posted(self) -> bool:
        return (self.status or "").lower() == self.STATUS_POSTED
