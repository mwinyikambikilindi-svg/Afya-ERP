from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class CashReceiptLine(Base):
    __tablename__ = "cash_receipt_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_receipt_id: Mapped[int] = mapped_column(ForeignKey("cash_receipts.id"), nullable=False)
    revenue_account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id"), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)