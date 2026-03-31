from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class NHIFImportBatch(Base):
    __tablename__ = "nhif_import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    claim_month: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nhif_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    imported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="imported")
    raw_text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
