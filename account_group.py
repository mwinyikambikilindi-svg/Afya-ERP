from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AccountGroup(Base):
    __tablename__ = "account_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_class_id: Mapped[int] = mapped_column(ForeignKey("account_classes.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("account_groups.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)