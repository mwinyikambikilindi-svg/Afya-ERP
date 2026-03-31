from __future__ import annotations

import csv
from pathlib import Path

from flask import current_app, redirect, render_template, request, url_for

from app.services.auth_service import login_required, role_required
from app.services.facility_service import (
    create_facility,
    delete_facility,
    get_facility,
    list_facilities,
    update_facility,
)


def register_facility_routes(flask_app):
    @flask_app.route("/facilities")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def facilities_index():
        rows = list_facilities()
        return render_template("facilities_index.html", rows=rows)

    @flask_app.route("/facilities/new", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def facilities_new():
        error_message = None
        if request.method == "POST":
            try:
                create_facility(
                    facility_code=request.form.get("facility_code"),
                    facility_name=request.form.get("facility_name"),
                    facility_type=request.form.get("facility_type"),
                    region=request.form.get("region"),
                    district=request.form.get("district"),
                    organization_id=int(request.form.get("organization_id")) if request.form.get("organization_id") else 1,
                )
                return redirect(url_for("facilities_index"))
            except Exception as e:
                current_app.logger.exception("Create facility error")
                error_message = str(e)
        return render_template("facilities_form.html", row=None, error_message=error_message)

    @flask_app.route("/facilities/<int:facility_pk>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def facilities_edit(facility_pk: int):
        error_message = None
        row = get_facility(facility_pk)
        if not row:
            return redirect(url_for("facilities_index"))

        if request.method == "POST":
            try:
                update_facility(
                    facility_pk=facility_pk,
                    facility_code=request.form.get("facility_code"),
                    facility_name=request.form.get("facility_name"),
                    facility_type=request.form.get("facility_type"),
                    region=request.form.get("region"),
                    district=request.form.get("district"),
                    organization_id=int(request.form.get("organization_id")) if request.form.get("organization_id") else row.get("organization_id") or 1,
                )
                return redirect(url_for("facilities_index"))
            except Exception as e:
                current_app.logger.exception("Update facility error")
                error_message = str(e)
                row = get_facility(facility_pk)

        return render_template("facilities_form.html", row=row, error_message=error_message)

    @flask_app.route("/facilities/<int:facility_pk>/delete", methods=["POST"])
    @login_required
    @role_required("ADMIN")
    def facilities_delete(facility_pk: int):
        try:
            delete_facility(facility_pk)
        except Exception:
            current_app.logger.exception("Delete facility error")
        return redirect(url_for("facilities_index"))

    @flask_app.route("/facilities/seed-pmu-38", methods=["POST"])
    @login_required
    @role_required("ADMIN")
    def facilities_seed_pmu_38():
        csv_path = Path(flask_app.root_path).parent / "data" / "pmu_facilities_38_master.csv"
        if not csv_path.exists():
            current_app.logger.error("PMU facilities CSV not found at %s", csv_path)
            return redirect(url_for("facilities_index"))

        try:
            existing = list_facilities()
            existing_names = {str(r.get("facility_name", "")).strip().lower() for r in existing}

            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = str(row.get("facility_name", "")).strip()
                    if not name or name.lower() in existing_names:
                        continue

                    try:
                        create_facility(
                            facility_code=row.get("facility_code"),
                            facility_name=name,
                            facility_type=row.get("facility_type"),
                            region=row.get("region"),
                            district=row.get("district"),
                            organization_id=1,
                        )
                    except Exception:
                        current_app.logger.exception("Seed single facility error")
                        continue
        except Exception:
            current_app.logger.exception("Seed facilities error")

        return redirect(url_for("facilities_index"))