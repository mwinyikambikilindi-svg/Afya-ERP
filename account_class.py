from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AccountClass(Base):
    __tablename__ = "account_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    normal_balance: Mapped[str] = mapped_column(String(10), nullable=False)