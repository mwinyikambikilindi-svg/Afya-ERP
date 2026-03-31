from __future__ import annotations
from datetime import date
from decimal import Decimal
from pathlib import Path
from flask import abort, current_app, redirect, render_template, request, send_from_directory, session as flask_session, url_for
from app.services.auth_service import login_required, role_required
from app.services.nhif_import_service import NHIFImportError, extract_pdf_text, parse_nhif_receipt_text, save_import_batch
from app.services.nhif_service import create_nhif_claim, create_nhif_collection, create_nhif_rejection, get_nhif_dashboard, get_nhif_reconciliation, list_nhif_claims, set_nhif_claim_status

def register_nhif_routes(flask_app):
    upload_dir = Path(flask_app.root_path).parent / "uploads" / "nhif"
    upload_dir.mkdir(parents=True, exist_ok=True)

    @flask_app.route("/nhif-import", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def nhif_import():
        error_message = None
        extracted = None
        if request.method == "POST" and request.files.get("pdf_file"):
            try:
                upload = request.files.get("pdf_file")
                if not upload or not upload.filename:
                    raise NHIFImportError("Chagua NHIF PDF kwanza.")
                safe_name = upload.filename.replace("/", "_").replace("\\\\", "_")
                file_path = upload_dir / safe_name
                upload.save(file_path)
                text = extract_pdf_text(str(file_path))
                extracted = parse_nhif_receipt_text(text)
                batch_id = save_import_batch(source_filename=safe_name, parsed=extracted, imported_by_user_id=flask_session.get("user_id"))
                return render_template("nhif_import.html", error_message=None, extracted=extracted, import_batch_id=batch_id)
            except Exception as e:
                current_app.logger.exception("NHIF import error")
                error_message = str(e)
        return render_template("nhif_import.html", error_message=error_message, extracted=extracted, import_batch_id=None)

    @flask_app.route("/nhif-claims", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def nhif_claims():
        error_message = None
        if request.method == "POST":
            try:
                claim_id = create_nhif_claim(
                    facility_name=request.form.get("facility_name"),
                    claim_month=request.form.get("claim_month"),
                    nhif_reference=request.form.get("nhif_reference"),
                    claim_date=request.form.get("claim_date"),
                    amount_claimed=request.form.get("amount_claimed"),
                    amount_paid=request.form.get("amount_paid"),
                    claim_forms_count=int(request.form.get("claim_forms_count")) if request.form.get("claim_forms_count") else None,
                    payment_reference=request.form.get("payment_reference"),
                    import_batch_id=int(request.form.get("import_batch_id")) if request.form.get("import_batch_id") else None,
                )

                amount_paid_raw = request.form.get("amount_paid")
                amount_paid = Decimal(str(amount_paid_raw).replace(",", "").strip()) if amount_paid_raw else Decimal("0.00")
                adjustment_raw = request.form.get("adjustment_total")
                adjustment_total = Decimal(str(adjustment_raw).replace(",", "").strip()) if adjustment_raw else Decimal("0.00")
                linked_errors = []

                if amount_paid > 0:
                    try:
                        create_nhif_collection(
                            claim_id=claim_id,
                            collection_date=request.form.get("claim_date"),
                            amount_collected=amount_paid,
                            receipt_reference=request.form.get("payment_reference"),
                            bank_reference=request.form.get("payment_reference"),
                        )
                    except Exception as e:
                        current_app.logger.exception("NHIF auto-collection error")
                        linked_errors.append(f"Auto-collection warning: {e}")

                if adjustment_total > 0:
                    try:
                        create_nhif_rejection(
                            claim_id=claim_id,
                            rejection_date=request.form.get("claim_date"),
                            rejection_reason="Imported automatically from NHIF payment variance / observed anomalies",
                            amount_rejected=adjustment_total,
                        )
                    except Exception as e:
                        current_app.logger.exception("NHIF auto-rejection error")
                        linked_errors.append(f"Auto-rejection warning: {e}")

                if linked_errors:
                    error_message = " | ".join(linked_errors)
                else:
                    return redirect(url_for("nhif_reconciliation"))
            except Exception as e:
                current_app.logger.exception("NHIF claims save error")
                error_message = str(e)

        rows = list_nhif_claims()
        return render_template("nhif_claims.html", rows=rows, error_message=error_message, today=date.today().isoformat())

    @flask_app.route("/nhif-claims/<int:claim_id>/approve", methods=["POST"])
    @login_required
    @role_required("ADMIN", "MANAGER")
    def approve_nhif_claim(claim_id: int):
        set_nhif_claim_status(claim_id, "approved", "approved")
        return redirect(url_for("nhif_claims"))

    @flask_app.route("/nhif-claims/<int:claim_id>/reject", methods=["POST"])
    @login_required
    @role_required("ADMIN", "MANAGER")
    def reject_nhif_claim(claim_id: int):
        set_nhif_claim_status(claim_id, "rejected", "rejected")
        return redirect(url_for("nhif_claims"))

    @flask_app.route("/nhif-pdf/<path:filename>")
    @login_required
    def nhif_pdf(filename: str):
        safe_name = filename.replace("/", "").replace("\\\\", "")
        file_path = upload_dir / safe_name
        if not file_path.exists():
            abort(404)
        return send_from_directory(upload_dir, safe_name, as_attachment=False)

    @flask_app.route("/nhif-collections", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def nhif_collections():
        error_message = None
        if request.method == "POST":
            try:
                create_nhif_collection(
                    claim_id=int(request.form.get("claim_id")),
                    collection_date=request.form.get("collection_date"),
                    amount_collected=request.form.get("amount_collected"),
                    receipt_reference=request.form.get("receipt_reference"),
                    bank_reference=request.form.get("bank_reference"),
                )
                return redirect(url_for("nhif_collections"))
            except Exception as e:
                current_app.logger.exception("NHIF collections error")
                error_message = str(e)
        rows = list_nhif_claims()
        return render_template("nhif_collections.html", rows=rows, error_message=error_message, today=date.today().isoformat())

    @flask_app.route("/nhif-rejections", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def nhif_rejections():
        error_message = None
        if request.method == "POST":
            try:
                create_nhif_rejection(
                    claim_id=int(request.form.get("claim_id")),
                    rejection_date=request.form.get("rejection_date"),
                    rejection_reason=request.form.get("rejection_reason"),
                    amount_rejected=request.form.get("amount_rejected"),
                )
                return redirect(url_for("nhif_rejections"))
            except Exception as e:
                current_app.logger.exception("NHIF rejections error")
                error_message = str(e)
        rows = list_nhif_claims()
        return render_template("nhif_rejections.html", rows=rows, error_message=error_message, today=date.today().isoformat())

    @flask_app.route("/nhif-reconciliation")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def nhif_reconciliation():
        rows = get_nhif_reconciliation()
        return render_template("nhif_reconciliation.html", rows=rows)

    @flask_app.route("/nhif-dashboard")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def nhif_dashboard():
        result = get_nhif_dashboard()
        return render_template("nhif_dashboard.html", result=result)
