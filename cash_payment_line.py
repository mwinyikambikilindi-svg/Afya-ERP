from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class CashPaymentLine(Base):
    __tablename__ = "cash_payment_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_payment_id: Mapped[int] = mapped_column(ForeignKey("cash_payments.id"), nullable=False)
    expense_account_id: Mapped[int] = mapped_column(ForeignKey("gl_accounts.id"), nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)