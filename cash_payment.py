from datetime import date
from sqlalchemy import String, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class CashPayment(Base):
    __tablename__ = "cash_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    cash_account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id"), nullable=False)

    payment_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")