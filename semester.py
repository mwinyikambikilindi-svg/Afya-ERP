from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "code", name="uq_semester_academic_year_code"),
        CheckConstraint("start_date <= end_date", name="ck_semester_date_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", back_populates="semesters")
    students: Mapped[list["Student"]] = relationship("Student", back_populates="current_semester")
    fee_structures: Mapped[list["FeeStructure"]] = relationship("FeeStructure", back_populates="semester")
    enrollments: Mapped[list["StudentEnrollment"]] = relationship("StudentEnrollment", back_populates="semester")

    def __repr__(self) -> str:
        return f"<Semester id={self.id} code={self.code!r} name={self.name!r}>"
