from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FeeStructure(Base):
    __tablename__ = "fee_structures"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"), nullable=True)
    semester_id: Mapped[int | None] = mapped_column(ForeignKey("semesters.id"), nullable=True)
    intake_id: Mapped[int | None] = mapped_column(ForeignKey("intakes.id"), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False, default="TZS")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    program: Mapped["Program | None"] = relationship("Program", back_populates="fee_structures")
    academic_year: Mapped["AcademicYear | None"] = relationship("AcademicYear", back_populates="fee_structures")
    semester: Mapped["Semester | None"] = relationship("Semester", back_populates="fee_structures")
    intake: Mapped["Intake | None"] = relationship("Intake", back_populates="fee_structures")
    lines: Mapped[list["FeeStructureLine"]] = relationship(
        "FeeStructureLine",
        back_populates="fee_structure",
        cascade="all, delete-orphan",
        order_by="FeeStructureLine.sort_order",
    )
    enrollments: Mapped[list["StudentEnrollment"]] = relationship("StudentEnrollment", back_populates="fee_structure")

    def __repr__(self) -> str:
        return f"<FeeStructure id={self.id} code={self.code!r} name={self.name!r}>"
