from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    award_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_in_semesters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    students: Mapped[list["Student"]] = relationship("Student", back_populates="program")
    fee_structures: Mapped[list["FeeStructure"]] = relationship("FeeStructure", back_populates="program")
    enrollments: Mapped[list["StudentEnrollment"]] = relationship("StudentEnrollment", back_populates="program")

    def __repr__(self) -> str:
        return f"<Program id={self.id} code={self.code!r} name={self.name!r}>"
