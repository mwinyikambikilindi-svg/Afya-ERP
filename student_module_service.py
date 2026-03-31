from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import app.extensions as ext
from sqlalchemy.orm import joinedload

from app.models.academic_year import AcademicYear
from app.models.fee_item import FeeItem
from app.models.fee_structure import FeeStructure
from app.models.fee_structure_line import FeeStructureLine
from app.models.gl_account import GLAccount
from app.models.intake import Intake
from app.models.program import Program
from app.models.semester import Semester
from app.models.student import Student
from app.models.student_enrollment import StudentEnrollment
from app.models.student_invoice import StudentInvoice
from app.models.student_invoice_line import StudentInvoiceLine
from app.models.student_payment import StudentPayment
from app.models.student_payment_allocation import StudentPaymentAllocation
from app.models.student_revenue_recognition_run import StudentRevenueRecognitionRun
from app.models.student_revenue_recognition_line import StudentRevenueRecognitionLine
from app.services.journal_service import create_journal_draft, post_journal


class StudentModuleError(Exception):
    pass


TWOPLACES = Decimal("0.01")


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized. Call init_db(app) first.")
    return ext.SessionLocal()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _parse_date(value: Any):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise StudentModuleError("Date si sahihi. Tumia YYYY-MM-DD.") from exc


def _to_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        raise StudentModuleError("Amount inahitajika.")
    try:
        return Decimal(str(value).replace(",", "").strip()).quantize(TWOPLACES)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise StudentModuleError("Amount lazima iwe namba sahihi.") from exc


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise StudentModuleError("ID si sahihi.") from exc


def _aggregate_journal_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[tuple[int, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for line in lines:
        gl_account_id = int(line["gl_account_id"])
        description = line.get("description") or "Student module posting"
        debit = Decimal(line.get("debit_amount", 0))
        credit = Decimal(line.get("credit_amount", 0))
        if debit > 0:
            bucket[(gl_account_id, f"D|{description}")] += debit
        if credit > 0:
            bucket[(gl_account_id, f"C|{description}")] += credit

    result: list[dict[str, Any]] = []
    for (gl_account_id, key), amount in bucket.items():
        side, description = key.split("|", 1)
        result.append(
            {
                "gl_account_id": gl_account_id,
                "description": description,
                "debit_amount": amount if side == "D" else Decimal("0.00"),
                "credit_amount": amount if side == "C" else Decimal("0.00"),
            }
        )
    return result


def generate_invoice_no() -> str:
    return f"SINV-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def generate_payment_no() -> str:
    return f"SPAY-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def list_programs() -> list[Program]:
    session = _new_session()
    try:
        return session.query(Program).order_by(Program.code.asc()).all()
    finally:
        session.close()


def create_program(code: str, name: str, award_type: str | None, duration_in_semesters: Any, description: str | None):
    code = (_clean_text(code) or "").upper()
    name = _clean_text(name)
    award_type = _clean_text(award_type)
    description = _clean_text(description)
    if not code:
        raise StudentModuleError("Weka program code.")
    if not name:
        raise StudentModuleError("Weka program name.")
    duration = None
    if duration_in_semesters not in (None, ""):
        try:
            duration = int(duration_in_semesters)
        except (TypeError, ValueError) as exc:
            raise StudentModuleError("Duration in semesters lazima iwe integer.") from exc
    session = _new_session()
    try:
        if session.query(Program).filter(Program.code == code).first():
            raise StudentModuleError("Program code tayari ipo.")
        if session.query(Program).filter(Program.name == name).first():
            raise StudentModuleError("Program name tayari ipo.")
        program = Program(code=code, name=name, award_type=award_type, duration_in_semesters=duration, description=description, is_active=True)
        session.add(program)
        session.commit()
        return program.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def create_academic_year(code: str, name: str, start_date: Any, end_date: Any):
    code = (_clean_text(code) or "").upper()
    name = _clean_text(name)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if not code:
        raise StudentModuleError("Weka academic year code.")
    if not name:
        raise StudentModuleError("Weka academic year name.")
    if not start or not end:
        raise StudentModuleError("Academic year start date na end date vinahitajika.")
    if start > end:
        raise StudentModuleError("Academic year start date haiwezi kuwa baada ya end date.")
    session = _new_session()
    try:
        if session.query(AcademicYear).filter(AcademicYear.code == code).first():
            raise StudentModuleError("Academic year code tayari ipo.")
        if session.query(AcademicYear).filter(AcademicYear.name == name).first():
            raise StudentModuleError("Academic year name tayari ipo.")
        row = AcademicYear(code=code, name=name, start_date=start, end_date=end, status="open", is_active=True)
        session.add(row)
        session.commit()
        return row.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def create_semester(academic_year_id: Any, code: str, name: str, start_date: Any, end_date: Any):
    code = (_clean_text(code) or "").upper()
    name = _clean_text(name)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if academic_year_id in (None, ""):
        raise StudentModuleError("Chagua academic year.")
    if not code:
        raise StudentModuleError("Weka semester code.")
    if not name:
        raise StudentModuleError("Weka semester name.")
    if not start or not end:
        raise StudentModuleError("Semester start date na end date vinahitajika.")
    if start > end:
        raise StudentModuleError("Semester start date haiwezi kuwa baada ya end date.")
    session = _new_session()
    try:
        academic_year = session.get(AcademicYear, int(academic_year_id))
        if not academic_year:
            raise StudentModuleError("Academic year haipo.")
        exists = session.query(Semester).filter(Semester.academic_year_id == academic_year.id, Semester.code == code).first()
        if exists:
            raise StudentModuleError("Semester code tayari ipo ndani ya academic year hiyo.")
        row = Semester(academic_year_id=academic_year.id, code=code, name=name, start_date=start, end_date=end, status="open", is_active=True)
        session.add(row)
        session.commit()
        return row.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def create_intake(academic_year_id: Any, code: str, name: str, start_date: Any, end_date: Any):
    code = (_clean_text(code) or "").upper()
    name = _clean_text(name)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if academic_year_id in (None, ""):
        raise StudentModuleError("Chagua academic year.")
    if not code:
        raise StudentModuleError("Weka intake code.")
    if not name:
        raise StudentModuleError("Weka intake name.")
    if not start or not end:
        raise StudentModuleError("Intake start date na end date vinahitajika.")
    if start > end:
        raise StudentModuleError("Intake start date haiwezi kuwa baada ya end date.")
    session = _new_session()
    try:
        academic_year = session.get(AcademicYear, int(academic_year_id))
        if not academic_year:
            raise StudentModuleError("Academic year haipo.")
        exists = session.query(Intake).filter(Intake.academic_year_id == academic_year.id, Intake.code == code).first()
        if exists:
            raise StudentModuleError("Intake code tayari ipo ndani ya academic year hiyo.")
        row = Intake(academic_year_id=academic_year.id, code=code, name=name, start_date=start, end_date=end, status="open", is_active=True)
        session.add(row)
        session.commit()
        return row.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_academic_years() -> list[AcademicYear]:
    session = _new_session()
    try:
        return session.query(AcademicYear).order_by(AcademicYear.start_date.desc()).all()
    finally:
        session.close()


def list_semesters() -> list[Semester]:
    session = _new_session()
    try:
        return session.query(Semester).order_by(Semester.start_date.desc()).all()
    finally:
        session.close()


def list_intakes() -> list[Intake]:
    session = _new_session()
    try:
        return session.query(Intake).order_by(Intake.start_date.desc()).all()
    finally:
        session.close()


def create_student(student_no: str, admission_no: str | None, first_name: str, middle_name: str | None, last_name: str,
                   gender: str | None, date_of_birth: Any, phone: str | None, email: str | None, national_id_no: str | None,
                   sponsor_name: str | None, guardian_name: str | None, guardian_phone: str | None, program_id: Any,
                   intake_id: Any, current_semester_id: Any, admission_date: Any, notes: str | None):
    student_no = (_clean_text(student_no) or "").upper()
    admission_no = (_clean_text(admission_no) or None)
    if admission_no:
        admission_no = admission_no.upper()
    first_name = _clean_text(first_name)
    middle_name = _clean_text(middle_name)
    last_name = _clean_text(last_name)
    gender = _clean_text(gender)
    dob = _parse_date(date_of_birth)
    admission = _parse_date(admission_date)
    phone = _clean_text(phone)
    email = _clean_text(email)
    national_id_no = _clean_text(national_id_no)
    sponsor_name = _clean_text(sponsor_name)
    guardian_name = _clean_text(guardian_name)
    guardian_phone = _clean_text(guardian_phone)
    notes = _clean_text(notes)
    if not student_no:
        raise StudentModuleError("Weka student number.")
    if not first_name or not last_name:
        raise StudentModuleError("Weka first name na last name.")
    session = _new_session()
    try:
        if session.query(Student).filter(Student.student_no == student_no).first():
            raise StudentModuleError("Student number tayari ipo.")
        if admission_no and session.query(Student).filter(Student.admission_no == admission_no).first():
            raise StudentModuleError("Admission number tayari ipo.")
        program = session.get(Program, int(program_id)) if program_id not in (None, "") else None
        intake = session.get(Intake, int(intake_id)) if intake_id not in (None, "") else None
        semester = session.get(Semester, int(current_semester_id)) if current_semester_id not in (None, "") else None
        student = Student(student_no=student_no, admission_no=admission_no, first_name=first_name, middle_name=middle_name,
                          last_name=last_name, gender=gender, date_of_birth=dob, phone=phone, email=email,
                          national_id_no=national_id_no, sponsor_name=sponsor_name, guardian_name=guardian_name,
                          guardian_phone=guardian_phone, program_id=program.id if program else None,
                          intake_id=intake.id if intake else None, current_semester_id=semester.id if semester else None,
                          admission_date=admission, status="active", notes=notes, is_active=True)
        session.add(student)
        session.flush()
        if program or intake or semester:
            academic_year_id = intake.academic_year_id if intake else (semester.academic_year_id if semester else None)
            fee_structure = None
            if program and academic_year_id:
                fee_structure = session.query(FeeStructure).filter(
                    FeeStructure.program_id == program.id,
                    FeeStructure.academic_year_id == academic_year_id,
                    FeeStructure.intake_id == (intake.id if intake else None),
                    FeeStructure.semester_id == (semester.id if semester else None),
                    FeeStructure.is_active == True,
                ).order_by(FeeStructure.id.desc()).first()
            enrollment = StudentEnrollment(student_id=student.id, program_id=program.id if program else None,
                                           academic_year_id=academic_year_id, semester_id=semester.id if semester else None,
                                           intake_id=intake.id if intake else None,
                                           fee_structure_id=fee_structure.id if fee_structure else None,
                                           enrollment_date=admission, status="active")
            session.add(enrollment)
        session.commit()
        return student.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_students() -> list[Student]:
    session = _new_session()
    try:
        return session.query(Student).options(joinedload(Student.program), joinedload(Student.intake), joinedload(Student.current_semester)).order_by(Student.id.desc()).all()
    finally:
        session.close()


def list_gl_accounts_for_mapping() -> list[GLAccount]:
    session = _new_session()
    try:
        return session.query(GLAccount).filter(GLAccount.is_active == True).order_by(GLAccount.code.asc()).all()
    finally:
        session.close()


def list_cash_accounts() -> list[GLAccount]:
    session = _new_session()
    try:
        return session.query(GLAccount).filter(GLAccount.is_active == True, GLAccount.code.in_(["1110", "1120", "1130"])).order_by(GLAccount.code.asc()).all()
    finally:
        session.close()


def create_fee_item(code: str, name: str, category: str, monetary_class: str, recognition_basis: str, is_refundable: bool,
                    description: str | None, gl_receivable_account_id: Any, gl_deferred_revenue_account_id: Any,
                    gl_revenue_account_id: Any, gl_discount_account_id: Any, gl_refund_account_id: Any,
                    gl_ecl_account_id: Any):
    code = (_clean_text(code) or "").upper(); name = _clean_text(name); category = (_clean_text(category) or "TUITION").upper()
    monetary_class = (_clean_text(monetary_class) or "monetary").lower(); recognition_basis = (_clean_text(recognition_basis) or "over_time").lower()
    description = _clean_text(description)
    if not code: raise StudentModuleError("Weka fee item code.")
    if not name: raise StudentModuleError("Weka fee item name.")
    session = _new_session()
    try:
        if session.query(FeeItem).filter(FeeItem.code == code).first(): raise StudentModuleError("Fee item code tayari ipo.")
        if session.query(FeeItem).filter(FeeItem.name == name).first(): raise StudentModuleError("Fee item name tayari ipo.")
        row = FeeItem(code=code, name=name, category=category, monetary_class=monetary_class, recognition_basis=recognition_basis,
                      is_refundable=bool(is_refundable), description=description,
                      gl_receivable_account_id=_optional_int(gl_receivable_account_id),
                      gl_deferred_revenue_account_id=_optional_int(gl_deferred_revenue_account_id),
                      gl_revenue_account_id=_optional_int(gl_revenue_account_id),
                      gl_discount_account_id=_optional_int(gl_discount_account_id),
                      gl_refund_account_id=_optional_int(gl_refund_account_id),
                      gl_ecl_account_id=_optional_int(gl_ecl_account_id), is_active=True)
        session.add(row); session.commit(); return row.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_fee_items() -> list[FeeItem]:
    session = _new_session()
    try:
        return session.query(FeeItem).order_by(FeeItem.code.asc()).all()
    finally:
        session.close()


def create_fee_structure(code: str, name: str, program_id: Any, academic_year_id: Any, semester_id: Any, intake_id: Any,
                         currency_code: str | None, notes: str | None):
    code = (_clean_text(code) or "").upper(); name = _clean_text(name); currency_code = (_clean_text(currency_code) or "TZS").upper(); notes = _clean_text(notes)
    if not code: raise StudentModuleError("Weka fee structure code.")
    if not name: raise StudentModuleError("Weka fee structure name.")
    session = _new_session()
    try:
        if session.query(FeeStructure).filter(FeeStructure.code == code).first(): raise StudentModuleError("Fee structure code tayari ipo.")
        if session.query(FeeStructure).filter(FeeStructure.name == name).first(): raise StudentModuleError("Fee structure name tayari ipo.")
        row = FeeStructure(code=code, name=name, program_id=_optional_int(program_id), academic_year_id=_optional_int(academic_year_id),
                           semester_id=_optional_int(semester_id), intake_id=_optional_int(intake_id), currency_code=currency_code,
                           status="draft", notes=notes, is_active=True)
        session.add(row); session.commit(); return row.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def add_fee_structure_line(fee_structure_id: Any, fee_item_id: Any, amount: Any, mandatory: bool, sort_order: Any):
    structure_id = _optional_int(fee_structure_id)
    item_id = _optional_int(fee_item_id)
    amt = _to_decimal(amount)
    order_value = int(sort_order) if sort_order not in (None, "") else 1
    if not structure_id: raise StudentModuleError("Chagua fee structure.")
    if not item_id: raise StudentModuleError("Chagua fee item.")
    if amt <= 0: raise StudentModuleError("Amount lazima iwe zaidi ya sifuri.")
    session = _new_session()
    try:
        structure = session.get(FeeStructure, structure_id)
        item = session.get(FeeItem, item_id)
        if not structure: raise StudentModuleError("Fee structure haipo.")
        if not item: raise StudentModuleError("Fee item haipo.")
        exists = session.query(FeeStructureLine).filter(FeeStructureLine.fee_structure_id == structure.id, FeeStructureLine.fee_item_id == item.id).first()
        if exists: raise StudentModuleError("Fee item tayari ipo kwenye structure hiyo.")
        line = FeeStructureLine(fee_structure_id=structure.id, fee_item_id=item.id, amount=amt, mandatory=bool(mandatory), sort_order=order_value)
        session.add(line); session.commit(); return line.id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_fee_structures() -> list[FeeStructure]:
    session = _new_session()
    try:
        return session.query(FeeStructure).options(joinedload(FeeStructure.program), joinedload(FeeStructure.academic_year), joinedload(FeeStructure.semester), joinedload(FeeStructure.intake), joinedload(FeeStructure.lines).joinedload(FeeStructureLine.fee_item)).order_by(FeeStructure.id.desc()).all()
    finally:
        session.close()


def list_student_enrollments() -> list[StudentEnrollment]:
    session = _new_session()
    try:
        return session.query(StudentEnrollment).options(joinedload(StudentEnrollment.student), joinedload(StudentEnrollment.program), joinedload(StudentEnrollment.academic_year), joinedload(StudentEnrollment.semester), joinedload(StudentEnrollment.intake), joinedload(StudentEnrollment.fee_structure)).order_by(StudentEnrollment.id.desc()).all()
    finally:
        session.close()


def _determine_recognition_account(fee_item: FeeItem) -> int | None:
    if (fee_item.recognition_basis or "").lower() == "on_invoice":
        return fee_item.gl_revenue_account_id
    return fee_item.gl_deferred_revenue_account_id or fee_item.gl_revenue_account_id


def create_student_invoice(enrollment_id: Any, invoice_date: Any, due_date: Any, reference_no: str | None, remarks: str | None,
                           auto_post: bool = False, draft_status: str = "draft"):
    enrollment_id = _optional_int(enrollment_id)
    inv_date = _parse_date(invoice_date)
    due = _parse_date(due_date)
    reference_no = _clean_text(reference_no)
    remarks = _clean_text(remarks)
    if not enrollment_id:
        raise StudentModuleError("Chagua student enrollment / fee structure context.")
    if not inv_date:
        raise StudentModuleError("Weka invoice date.")
    session = _new_session()
    try:
        enrollment = session.query(StudentEnrollment).options(joinedload(StudentEnrollment.student), joinedload(StudentEnrollment.fee_structure).joinedload(FeeStructure.lines).joinedload(FeeStructureLine.fee_item)).filter(StudentEnrollment.id == enrollment_id).first()
        if not enrollment:
            raise StudentModuleError("Enrollment haipo.")
        if not enrollment.student:
            raise StudentModuleError("Enrollment haina student.")
        if not enrollment.fee_structure:
            raise StudentModuleError("Enrollment hii haina fee structure. Weka fee structure kwanza.")
        if not enrollment.fee_structure.lines:
            raise StudentModuleError("Fee structure haina lines. Ongeza fee items kwanza.")

        invoice = StudentInvoice(student_id=enrollment.student_id, enrollment_id=enrollment.id, invoice_no=generate_invoice_no(),
                                 invoice_date=inv_date, due_date=due, reference_no=reference_no,
                                 currency_code=enrollment.fee_structure.currency_code or "TZS", remarks=remarks,
                                 total_amount=Decimal("0.00"), paid_amount=Decimal("0.00"), balance_amount=Decimal("0.00"),
                                 status=draft_status)
        session.add(invoice)
        session.flush()

        total = Decimal("0.00")
        for row in enrollment.fee_structure.lines:
            item = row.fee_item
            if not item:
                continue
            if not item.gl_receivable_account_id:
                raise StudentModuleError(f"Fee item {item.code} haina receivable GL mapping.")
            recognition_gl = _determine_recognition_account(item)
            if not recognition_gl:
                raise StudentModuleError(f"Fee item {item.code} haina revenue/deferred GL mapping.")
            amount = Decimal(row.amount).quantize(TWOPLACES)
            line = StudentInvoiceLine(
                invoice_id=invoice.id,
                fee_item_id=item.id,
                description=f"{item.code} - {item.name}",
                amount=amount,
                paid_amount=Decimal("0.00"),
                balance_amount=amount,
                receivable_gl_account_id=item.gl_receivable_account_id,
                recognition_gl_account_id=recognition_gl,
                recognition_basis=item.recognition_basis,
                monetary_class=item.monetary_class,
            )
            session.add(line)
            total += amount

        invoice.total_amount = total
        invoice.balance_amount = total
        session.commit()
        invoice_id = invoice.id
        invoice_no = invoice.invoice_no
    except Exception:
        session.rollback(); raise
    finally:
        session.close()

    if auto_post:
        post_student_invoice(invoice_id)
    return {"invoice_id": invoice_id, "invoice_no": invoice_no}


def post_student_invoice(invoice_id: Any):
    invoice_id = _optional_int(invoice_id)
    if not invoice_id:
        raise StudentModuleError("Invoice ID si sahihi.")
    session = _new_session()
    try:
        invoice = session.query(StudentInvoice).options(joinedload(StudentInvoice.lines), joinedload(StudentInvoice.student)).filter(StudentInvoice.id == invoice_id).first()
        if not invoice:
            raise StudentModuleError("Student invoice haipo.")
        if invoice.status in {"posted", "partially_paid", "paid"}:
            raise StudentModuleError("Invoice hii tayari imepostiwa.")
        if not invoice.lines:
            raise StudentModuleError("Invoice haina lines.")
        journal_lines = []
        for line in invoice.lines:
            if not line.receivable_gl_account_id or not line.recognition_gl_account_id:
                raise StudentModuleError("Invoice line ina GL mapping isiyokamilika.")
            desc = line.description or f"Student invoice {invoice.invoice_no}"
            journal_lines.append({"gl_account_id": int(line.receivable_gl_account_id), "description": desc, "debit_amount": Decimal(line.amount), "credit_amount": Decimal("0.00")})
            journal_lines.append({"gl_account_id": int(line.recognition_gl_account_id), "description": desc, "debit_amount": Decimal("0.00"), "credit_amount": Decimal(line.amount)})
        batch_id = create_journal_draft(branch_id=1, journal_date=invoice.invoice_date, source_module="STUDENT_INVOICE", reference_no=invoice.invoice_no, narration=invoice.remarks or f"Student invoice {invoice.invoice_no}", lines=_aggregate_journal_lines(journal_lines))
        post_journal(batch_id)
        invoice.journal_batch_id = batch_id
        invoice.status = "posted"
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_student_invoices() -> list[StudentInvoice]:
    session = _new_session()
    try:
        return session.query(StudentInvoice).options(joinedload(StudentInvoice.student), joinedload(StudentInvoice.enrollment).joinedload(StudentEnrollment.program), joinedload(StudentInvoice.enrollment).joinedload(StudentEnrollment.semester), joinedload(StudentInvoice.lines)).order_by(StudentInvoice.id.desc()).all()
    finally:
        session.close()


def create_student_payment(student_id: Any, cash_account_id: Any, payment_date: Any, amount: Any, reference_no: str | None,
                           remarks: str | None, auto_post: bool = False, draft_status: str = "draft"):
    student_id = _optional_int(student_id)
    cash_account_id = _optional_int(cash_account_id)
    pay_date = _parse_date(payment_date)
    total_amount = _to_decimal(amount)
    reference_no = _clean_text(reference_no)
    remarks = _clean_text(remarks)
    if not student_id:
        raise StudentModuleError("Chagua student.")
    if not cash_account_id:
        raise StudentModuleError("Chagua cash/bank account.")
    if not pay_date:
        raise StudentModuleError("Weka payment date.")
    if total_amount <= 0:
        raise StudentModuleError("Payment amount lazima iwe zaidi ya sifuri.")
    session = _new_session()
    try:
        student = session.get(Student, student_id)
        if not student:
            raise StudentModuleError("Student haipo.")
        cash_account = session.get(GLAccount, cash_account_id)
        if not cash_account or getattr(cash_account, "is_active", True) is False:
            raise StudentModuleError("Cash/Bank account haipo au imefungwa.")

        open_lines = session.query(StudentInvoiceLine).join(StudentInvoice, StudentInvoiceLine.invoice_id == StudentInvoice.id).filter(
            StudentInvoice.student_id == student_id,
            StudentInvoice.status.in_(["posted", "partially_paid"]),
            StudentInvoiceLine.balance_amount > 0,
        ).order_by(StudentInvoice.invoice_date.asc(), StudentInvoice.id.asc(), StudentInvoiceLine.id.asc()).all()

        total_open = sum((Decimal(line.balance_amount) for line in open_lines), Decimal("0.00"))
        if total_open <= 0:
            raise StudentModuleError("Student huyu hana receivable ya kulipwa kwa sasa.")
        if total_amount > total_open:
            raise StudentModuleError(f"Payment amount haiwezi kuzidi outstanding balance ya {total_open}.")

        payment = StudentPayment(student_id=student_id, cash_account_id=cash_account_id, payment_no=generate_payment_no(), payment_date=pay_date,
                                 reference_no=reference_no, remarks=remarks, total_amount=total_amount,
                                 allocated_amount=Decimal("0.00"), unallocated_amount=total_amount, status=draft_status)
        session.add(payment)
        session.flush()

        remaining = total_amount
        allocated_total = Decimal("0.00")
        for line in open_lines:
            if remaining <= 0:
                break
            open_amt = Decimal(line.balance_amount)
            alloc = open_amt if open_amt <= remaining else remaining
            if alloc <= 0:
                continue
            session.add(StudentPaymentAllocation(payment_id=payment.id, invoice_id=line.invoice_id, invoice_line_id=line.id, allocated_amount=alloc))
            remaining -= alloc
            allocated_total += alloc

        payment.allocated_amount = allocated_total
        payment.unallocated_amount = total_amount - allocated_total
        session.commit()
        payment_id = payment.id
        payment_no = payment.payment_no
    except Exception:
        session.rollback(); raise
    finally:
        session.close()

    if auto_post:
        post_student_payment(payment_id)
    return {"payment_id": payment_id, "payment_no": payment_no}


def post_student_payment(payment_id: Any):
    payment_id = _optional_int(payment_id)
    if not payment_id:
        raise StudentModuleError("Payment ID si sahihi.")
    session = _new_session()
    try:
        payment = session.query(StudentPayment).options(joinedload(StudentPayment.student), joinedload(StudentPayment.allocations).joinedload(StudentPaymentAllocation.invoice_line), joinedload(StudentPayment.allocations).joinedload(StudentPaymentAllocation.invoice)).filter(StudentPayment.id == payment_id).first()
        if not payment:
            raise StudentModuleError("Student payment haipo.")
        if payment.status == "posted":
            raise StudentModuleError("Payment hii tayari imepostiwa.")
        if not payment.allocations:
            raise StudentModuleError("Payment haina allocations.")

        journal_lines = [{"gl_account_id": int(payment.cash_account_id), "description": f"Student payment {payment.payment_no}", "debit_amount": Decimal(payment.total_amount), "credit_amount": Decimal("0.00")}]
        credit_by_receivable: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))

        invoice_map = {}
        for alloc in payment.allocations:
            line = alloc.invoice_line
            invoice = alloc.invoice
            if not line or not invoice:
                raise StudentModuleError("Payment allocation imeharibika.")
            if Decimal(line.balance_amount) < Decimal(alloc.allocated_amount):
                raise StudentModuleError("Allocation amount inazidi invoice line balance ya sasa.")

            line.paid_amount = Decimal(line.paid_amount) + Decimal(alloc.allocated_amount)
            line.balance_amount = Decimal(line.balance_amount) - Decimal(alloc.allocated_amount)
            credit_by_receivable[int(line.receivable_gl_account_id)] += Decimal(alloc.allocated_amount)
            invoice_map[invoice.id] = invoice

        for account_id, amount in credit_by_receivable.items():
            journal_lines.append({"gl_account_id": account_id, "description": f"Receivable settlement {payment.payment_no}", "debit_amount": Decimal("0.00"), "credit_amount": amount})

        batch_id = create_journal_draft(branch_id=1, journal_date=payment.payment_date, source_module="STUDENT_PAYMENT", reference_no=payment.payment_no, narration=payment.remarks or f"Student payment {payment.payment_no}", lines=_aggregate_journal_lines(journal_lines))
        post_journal(batch_id)
        payment.journal_batch_id = batch_id
        payment.status = "posted"

        for invoice in invoice_map.values():
            total_paid = sum((Decimal(line.paid_amount) for line in invoice.lines), Decimal("0.00"))
            total_balance = sum((Decimal(line.balance_amount) for line in invoice.lines), Decimal("0.00"))
            invoice.paid_amount = total_paid
            invoice.balance_amount = total_balance
            if total_balance <= 0:
                invoice.status = "paid"
            elif total_paid > 0:
                invoice.status = "partially_paid"
            elif invoice.journal_batch_id:
                invoice.status = "posted"

        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_student_payments() -> list[StudentPayment]:
    session = _new_session()
    try:
        return session.query(StudentPayment).options(joinedload(StudentPayment.student), joinedload(StudentPayment.allocations)).order_by(StudentPayment.id.desc()).all()
    finally:
        session.close()


def list_student_receivables():
    session = _new_session()
    try:
        students = session.query(Student).options(joinedload(Student.program)).order_by(Student.student_no.asc()).all()
        result = []
        for student in students:
            invoices = session.query(StudentInvoice).filter(StudentInvoice.student_id == student.id, StudentInvoice.status.in_(["posted", "partially_paid", "paid"])) .all()
            billed = sum((Decimal(inv.total_amount) for inv in invoices), Decimal("0.00"))
            paid = sum((Decimal(inv.paid_amount) for inv in invoices), Decimal("0.00"))
            balance = sum((Decimal(inv.balance_amount) for inv in invoices), Decimal("0.00"))
            if billed == paid == balance == 0:
                continue
            result.append({
                "student_id": student.id,
                "student_no": student.student_no,
                "student_name": student.full_name,
                "program_name": student.program.name if student.program else "",
                "total_billed": billed,
                "total_paid": paid,
                "total_balance": balance,
                "status": "Cleared" if balance <= 0 else ("Partially Paid" if paid > 0 else "Outstanding"),
            })
        return result
    finally:
        session.close()


def get_student_statement(student_id: Any):
    student_id = _optional_int(student_id)
    if not student_id:
        raise StudentModuleError("Student ID si sahihi.")
    session = _new_session()
    try:
        student = session.query(Student).options(joinedload(Student.program), joinedload(Student.intake), joinedload(Student.current_semester)).filter(Student.id == student_id).first()
        if not student:
            raise StudentModuleError("Student haipo.")
        invoices = session.query(StudentInvoice).options(joinedload(StudentInvoice.lines)).filter(StudentInvoice.student_id == student_id).order_by(StudentInvoice.invoice_date.asc(), StudentInvoice.id.asc()).all()
        payments = session.query(StudentPayment).options(joinedload(StudentPayment.allocations).joinedload(StudentPaymentAllocation.invoice)).filter(StudentPayment.student_id == student_id).order_by(StudentPayment.payment_date.asc(), StudentPayment.id.asc()).all()
        summary = {
            "total_billed": sum((Decimal(inv.total_amount) for inv in invoices), Decimal("0.00")),
            "total_paid": sum((Decimal(inv.paid_amount) for inv in invoices), Decimal("0.00")),
            "total_balance": sum((Decimal(inv.balance_amount) for inv in invoices), Decimal("0.00")),
        }
        return {"student": student, "invoices": invoices, "payments": payments, "summary": summary}
    finally:
        session.close()



def generate_revenue_run_no() -> str:
    return f"SRR-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _service_window_for_enrollment(enrollment: StudentEnrollment | None, fallback_date):
    if enrollment and enrollment.semester:
        return enrollment.semester.start_date, enrollment.semester.end_date
    if enrollment and enrollment.academic_year:
        return enrollment.academic_year.start_date, enrollment.academic_year.end_date
    return fallback_date, fallback_date


def _recognition_progress(as_of_date, start_date, end_date) -> Decimal:
    if not start_date or not end_date:
        return Decimal("1.0000")
    if as_of_date <= start_date:
        return Decimal("0.0000")
    if as_of_date >= end_date:
        return Decimal("1.0000")
    total_days = (end_date - start_date).days + 1
    elapsed_days = (as_of_date - start_date).days + 1
    if total_days <= 0:
        return Decimal("1.0000")
    return (Decimal(elapsed_days) / Decimal(total_days)).quantize(Decimal("0.0001"))


def _already_recognized_amount(session, invoice_line_id: int) -> Decimal:
    rows = session.query(StudentRevenueRecognitionLine).join(
        StudentRevenueRecognitionRun,
        StudentRevenueRecognitionLine.run_id == StudentRevenueRecognitionRun.id,
    ).filter(
        StudentRevenueRecognitionLine.invoice_line_id == invoice_line_id,
        StudentRevenueRecognitionRun.status == "posted",
    ).all()
    return sum((Decimal(row.recognized_amount) for row in rows), Decimal("0.00"))


def run_student_revenue_recognition(as_of_date: Any, remarks: str | None, auto_post: bool = False, draft_status: str = "draft"):
    recognition_date = _parse_date(as_of_date)
    remarks = _clean_text(remarks)
    if not recognition_date:
        raise StudentModuleError("Weka recognition as-of date.")

    session = _new_session()
    try:
        invoices = session.query(StudentInvoice).options(
            joinedload(StudentInvoice.lines).joinedload(StudentInvoiceLine.fee_item),
            joinedload(StudentInvoice.enrollment).joinedload(StudentEnrollment.semester),
            joinedload(StudentInvoice.enrollment).joinedload(StudentEnrollment.academic_year),
            joinedload(StudentInvoice.student),
        ).filter(StudentInvoice.status.in_(["posted", "partially_paid", "paid"])).order_by(StudentInvoice.invoice_date.asc(), StudentInvoice.id.asc()).all()

        run = StudentRevenueRecognitionRun(
            run_no=generate_revenue_run_no(),
            as_of_date=recognition_date,
            remarks=remarks,
            total_recognized_amount=Decimal("0.00"),
            status=draft_status,
        )
        session.add(run)
        session.flush()

        total_recognized = Decimal("0.00")
        for invoice in invoices:
            start_date, end_date = _service_window_for_enrollment(invoice.enrollment, invoice.invoice_date)
            progress = _recognition_progress(recognition_date, start_date, end_date)
            for line in invoice.lines:
                fee_item = line.fee_item
                if not fee_item:
                    continue
                if (line.recognition_basis or "").lower() == "on_invoice":
                    continue
                deferred_gl = fee_item.gl_deferred_revenue_account_id
                revenue_gl = fee_item.gl_revenue_account_id
                if not deferred_gl or not revenue_gl:
                    continue

                gross_amount = Decimal(line.amount)
                cumulative_target = (gross_amount * progress).quantize(TWOPLACES)
                already_recognized = _already_recognized_amount(session, line.id)
                delta = (cumulative_target - already_recognized).quantize(TWOPLACES)
                if delta <= 0:
                    continue

                session.add(StudentRevenueRecognitionLine(
                    run_id=run.id,
                    invoice_id=invoice.id,
                    invoice_line_id=line.id,
                    fee_item_id=fee_item.id,
                    deferred_gl_account_id=deferred_gl,
                    revenue_gl_account_id=revenue_gl,
                    service_start_date=start_date,
                    service_end_date=end_date,
                    progress_percent=progress,
                    recognized_amount=delta,
                ))
                total_recognized += delta

        if total_recognized <= 0:
            raise StudentModuleError("Hakuna deferred tuition mpya ya ku-recognize kwa tarehe hiyo.")

        run.total_recognized_amount = total_recognized
        session.commit()
        run_id = run.id
        run_no = run.run_no
    except Exception:
        session.rollback(); raise
    finally:
        session.close()

    if auto_post:
        post_student_revenue_recognition(run_id)
    return {"run_id": run_id, "run_no": run_no}


def post_student_revenue_recognition(run_id: Any):
    run_id = _optional_int(run_id)
    if not run_id:
        raise StudentModuleError("Revenue recognition run ID si sahihi.")
    session = _new_session()
    try:
        run = session.query(StudentRevenueRecognitionRun).options(
            joinedload(StudentRevenueRecognitionRun.lines)
        ).filter(StudentRevenueRecognitionRun.id == run_id).first()
        if not run:
            raise StudentModuleError("Revenue recognition run haipo.")
        if run.status == "posted":
            raise StudentModuleError("Run hii tayari imepostiwa.")
        if not run.lines:
            raise StudentModuleError("Run haina lines za posting.")

        journal_lines = []
        for line in run.lines:
            amount = Decimal(line.recognized_amount)
            journal_lines.append({
                "gl_account_id": int(line.deferred_gl_account_id),
                "description": f"Deferred tuition recognition {run.run_no}",
                "debit_amount": amount,
                "credit_amount": Decimal("0.00"),
            })
            journal_lines.append({
                "gl_account_id": int(line.revenue_gl_account_id),
                "description": f"Tuition revenue recognition {run.run_no}",
                "debit_amount": Decimal("0.00"),
                "credit_amount": amount,
            })

        batch_id = create_journal_draft(
            branch_id=1,
            journal_date=run.as_of_date,
            source_module="STUDENT_REVENUE_RECOGNITION",
            reference_no=run.run_no,
            narration=run.remarks or f"Student revenue recognition {run.run_no}",
            lines=_aggregate_journal_lines(journal_lines),
        )
        post_journal(batch_id)
        run.journal_batch_id = batch_id
        run.status = "posted"
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_student_revenue_runs():
    session = _new_session()
    try:
        return session.query(StudentRevenueRecognitionRun).options(
            joinedload(StudentRevenueRecognitionRun.lines)
        ).order_by(StudentRevenueRecognitionRun.id.desc()).all()
    finally:
        session.close()


def get_student_aging_report(as_of_date: Any):
    report_date = _parse_date(as_of_date)
    if not report_date:
        raise StudentModuleError("Weka aging as-of date.")
    session = _new_session()
    try:
        invoices = session.query(StudentInvoice).options(
            joinedload(StudentInvoice.student).joinedload(Student.program),
            joinedload(StudentInvoice.enrollment).joinedload(StudentEnrollment.program),
        ).filter(StudentInvoice.status.in_(["posted", "partially_paid"])).order_by(StudentInvoice.invoice_date.asc()).all()
        rows = []
        totals = {
            "current": Decimal("0.00"),
            "days_1_30": Decimal("0.00"),
            "days_31_60": Decimal("0.00"),
            "days_61_90": Decimal("0.00"),
            "days_over_90": Decimal("0.00"),
            "total_balance": Decimal("0.00"),
        }
        for invoice in invoices:
            balance = Decimal(invoice.balance_amount)
            if balance <= 0:
                continue
            due_date = invoice.due_date or invoice.invoice_date
            days_past_due = max((report_date - due_date).days, 0)
            buckets = {
                "current": Decimal("0.00"),
                "days_1_30": Decimal("0.00"),
                "days_31_60": Decimal("0.00"),
                "days_61_90": Decimal("0.00"),
                "days_over_90": Decimal("0.00"),
            }
            if days_past_due <= 0:
                buckets["current"] = balance
            elif days_past_due <= 30:
                buckets["days_1_30"] = balance
            elif days_past_due <= 60:
                buckets["days_31_60"] = balance
            elif days_past_due <= 90:
                buckets["days_61_90"] = balance
            else:
                buckets["days_over_90"] = balance
            for key, value in buckets.items():
                totals[key] += value
            totals["total_balance"] += balance
            rows.append({
                "invoice_id": invoice.id,
                "invoice_no": invoice.invoice_no,
                "student_id": invoice.student_id,
                "student_no": invoice.student.student_no if invoice.student else "",
                "student_name": invoice.student.full_name if invoice.student else "",
                "program_name": (invoice.student.program.name if invoice.student and invoice.student.program else ""),
                "sponsor_name": invoice.student.sponsor_name if invoice.student else "",
                "invoice_date": invoice.invoice_date,
                "due_date": due_date,
                "days_past_due": days_past_due,
                **buckets,
                "total_balance": balance,
            })
        return {"as_of_date": report_date, "rows": rows, "totals": totals}
    finally:
        session.close()


def get_student_collections_dashboard(date_from: Any, date_to: Any):
    start_date = _parse_date(date_from)
    end_date = _parse_date(date_to)
    if not start_date or not end_date:
        raise StudentModuleError("Weka date_from na date_to.")
    if start_date > end_date:
        raise StudentModuleError("date_from haiwezi kuwa baada ya date_to.")

    session = _new_session()
    try:
        invoices = session.query(StudentInvoice).options(
            joinedload(StudentInvoice.student).joinedload(Student.program)
        ).filter(StudentInvoice.invoice_date >= start_date, StudentInvoice.invoice_date <= end_date).all()
        payments = session.query(StudentPayment).options(
            joinedload(StudentPayment.student).joinedload(Student.program)
        ).filter(StudentPayment.payment_date >= start_date, StudentPayment.payment_date <= end_date).all()
        all_open_invoices = session.query(StudentInvoice).filter(StudentInvoice.status.in_(["posted", "partially_paid"])).all()

        billed_total = sum((Decimal(inv.total_amount) for inv in invoices), Decimal("0.00"))
        collected_total = sum((Decimal(pay.total_amount) for pay in payments if pay.status == "posted"), Decimal("0.00"))
        unposted_payment_total = sum((Decimal(pay.total_amount) for pay in payments if pay.status != "posted"), Decimal("0.00"))
        outstanding_total = sum((Decimal(inv.balance_amount) for inv in all_open_invoices), Decimal("0.00"))
        unallocated_total = sum((Decimal(pay.unallocated_amount) for pay in payments), Decimal("0.00"))

        collections_by_program: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for pay in payments:
            if pay.status != "posted":
                continue
            program_name = pay.student.program.name if pay.student and pay.student.program else "Unassigned"
            collections_by_program[program_name] += Decimal(pay.total_amount)

        invoice_count = len(invoices)
        paid_count = len([p for p in payments if p.status == "posted"])
        collection_rate = Decimal("0.00")
        if billed_total > 0:
            collection_rate = ((collected_total / billed_total) * Decimal("100.00")).quantize(TWOPLACES)

        return {
            "date_from": start_date,
            "date_to": end_date,
            "summary": {
                "billed_total": billed_total,
                "collected_total": collected_total,
                "unposted_payment_total": unposted_payment_total,
                "outstanding_total": outstanding_total,
                "unallocated_total": unallocated_total,
                "invoice_count": invoice_count,
                "posted_payment_count": paid_count,
                "collection_rate": collection_rate,
            },
            "collections_by_program": [
                {"program_name": name, "amount": amount}
                for name, amount in sorted(collections_by_program.items(), key=lambda x: x[0])
            ],
        }
    finally:
        session.close()


def list_sponsor_balances():
    session = _new_session()
    try:
        students = session.query(Student).options(joinedload(Student.program)).filter(Student.sponsor_name.isnot(None)).order_by(Student.sponsor_name.asc(), Student.student_no.asc()).all()
        bucket: dict[str, dict[str, Any]] = {}
        for student in students:
            sponsor = (student.sponsor_name or "").strip()
            if not sponsor:
                continue
            invoices = session.query(StudentInvoice).filter(StudentInvoice.student_id == student.id, StudentInvoice.status.in_(["posted", "partially_paid", "paid"])).all()
            billed = sum((Decimal(inv.total_amount) for inv in invoices), Decimal("0.00"))
            paid = sum((Decimal(inv.paid_amount) for inv in invoices), Decimal("0.00"))
            balance = sum((Decimal(inv.balance_amount) for inv in invoices), Decimal("0.00"))
            if sponsor not in bucket:
                bucket[sponsor] = {
                    "sponsor_name": sponsor,
                    "student_count": 0,
                    "total_billed": Decimal("0.00"),
                    "total_paid": Decimal("0.00"),
                    "total_balance": Decimal("0.00"),
                }
            bucket[sponsor]["student_count"] += 1
            bucket[sponsor]["total_billed"] += billed
            bucket[sponsor]["total_paid"] += paid
            bucket[sponsor]["total_balance"] += balance
        return sorted(bucket.values(), key=lambda x: x["sponsor_name"])
    finally:
        session.close()


def get_sponsor_statement(sponsor_name: str):
    sponsor_name = _clean_text(sponsor_name)
    if not sponsor_name:
        raise StudentModuleError("Sponsor name inahitajika.")
    session = _new_session()
    try:
        students = session.query(Student).options(joinedload(Student.program)).filter(Student.sponsor_name == sponsor_name).order_by(Student.student_no.asc()).all()
        if not students:
            raise StudentModuleError("Sponsor huyo hana student records.")
        rows = []
        total_billed = Decimal("0.00")
        total_paid = Decimal("0.00")
        total_balance = Decimal("0.00")
        for student in students:
            invoices = session.query(StudentInvoice).filter(StudentInvoice.student_id == student.id).order_by(StudentInvoice.invoice_date.asc()).all()
            billed = sum((Decimal(inv.total_amount) for inv in invoices), Decimal("0.00"))
            paid = sum((Decimal(inv.paid_amount) for inv in invoices), Decimal("0.00"))
            balance = sum((Decimal(inv.balance_amount) for inv in invoices), Decimal("0.00"))
            rows.append({
                "student_id": student.id,
                "student_no": student.student_no,
                "student_name": student.full_name,
                "program_name": student.program.name if student.program else "",
                "total_billed": billed,
                "total_paid": paid,
                "total_balance": balance,
            })
            total_billed += billed
            total_paid += paid
            total_balance += balance
        return {
            "sponsor_name": sponsor_name,
            "rows": rows,
            "summary": {
                "total_billed": total_billed,
                "total_paid": total_paid,
                "total_balance": total_balance,
            },
        }
    finally:
        session.close()
