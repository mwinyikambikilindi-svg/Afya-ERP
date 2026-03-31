from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AcademicYear(Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_academic_year_date_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    semesters: Mapped[list["Semester"]] = relationship("Semester", back_populates="academic_year")
    intakes: Mapped[list["Intake"]] = relationship("Intake", back_populates="academic_year")
    fee_structures: Mapped[list["FeeStructure"]] = relationship("FeeStructure", back_populates="academic_year")
    enrollments: Mapped[list["StudentEnrollment"]] = relationship("StudentEnrollment", back_populates="academic_year")

    def __repr__(self) -> str:
        return f"<AcademicYear id={self.id} name={self.name!r}>"
