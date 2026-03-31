from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentEnrollment(Base):
    __tablename__ = "student_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"), nullable=True)
    semester_id: Mapped[int | None] = mapped_column(ForeignKey("semesters.id"), nullable=True)
    intake_id: Mapped[int | None] = mapped_column(ForeignKey("intakes.id"), nullable=True)
    fee_structure_id: Mapped[int | None] = mapped_column(ForeignKey("fee_structures.id"), nullable=True)
    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    student: Mapped["Student"] = relationship("Student", back_populates="enrollments")
    program: Mapped["Program | None"] = relationship("Program", back_populates="enrollments")
    academic_year: Mapped["AcademicYear | None"] = relationship("AcademicYear", back_populates="enrollments")
    semester: Mapped["Semester | None"] = relationship("Semester", back_populates="enrollments")
    intake: Mapped["Intake | None"] = relationship("Intake", back_populates="enrollments")
    fee_structure: Mapped["FeeStructure | None"] = relationship("FeeStructure", back_populates="enrollments")

    def __repr__(self) -> str:
        return f"<StudentEnrollment id={self.id} student_id={self.student_id} status={self.status!r}>"
