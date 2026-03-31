from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class GLAccount(Base):
    __tablename__ = "gl_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_group_id: Mapped[int] = mapped_column(ForeignKey("account_groups.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("gl_accounts.id"), nullable=True)

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)

    account_type: Mapped[str] = mapped_column(String(20), nullable=False, default="posting")
    allow_manual_posting: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_subledger: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_cost_center: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_department: Mapped[bool] = mapped_column(Boolean, default=False)
    is_control_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)