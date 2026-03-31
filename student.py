from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_no: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    admission_no: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    national_id_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sponsor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    intake_id: Mapped[int | None] = mapped_column(ForeignKey("intakes.id"), nullable=True)
    current_semester_id: Mapped[int | None] = mapped_column(ForeignKey("semesters.id"), nullable=True)
    admission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    program: Mapped["Program | None"] = relationship("Program", back_populates="students")
    intake: Mapped["Intake | None"] = relationship("Intake", back_populates="students")
    current_semester: Mapped["Semester | None"] = relationship("Semester", back_populates="students")
    enrollments: Mapped[list["StudentEnrollment"]] = relationship("StudentEnrollment", back_populates="student")

    @property
    def full_name(self) -> str:
        names = [self.first_name, self.middle_name, self.last_name]
        return " ".join([name for name in names if name])

    def __repr__(self) -> str:
        return f"<Student id={self.id} student_no={self.student_no!r} name={self.full_name!r}>"
