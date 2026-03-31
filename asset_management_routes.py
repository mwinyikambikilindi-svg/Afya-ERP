from __future__ import annotations

from datetime import date

from flask import redirect, render_template, request, session as flask_session, url_for

import app.extensions as ext
from app.models.asset_category import AssetCategory
from app.models.asset_custodian import AssetCustodian
from app.models.asset_location import AssetLocation
from app.models.branch import Branch
from app.models.fixed_asset import FixedAsset
from app.models.gl_account import GLAccount
from app.models.supplier import Supplier
from app.services.audit_log_service import log_audit_event
from app.services.asset_management_service import (
    AssetManagementError,
    approve_asset_acquisition,
    approve_asset_depreciation_run,
    approve_asset_disposal,
    asset_report_summary,
    create_asset_acquisition,
    create_asset_category,
    create_asset_custodian,
    create_asset_disposal,
    create_asset_location,
    create_asset_maintenance,
    create_fixed_asset,
    list_asset_acquisitions,
    list_asset_categories,
    list_asset_custodians,
    list_asset_depreciation_runs,
    list_asset_disposals,
    list_asset_locations,
    list_asset_maintenance,
    list_fixed_assets,
    run_asset_depreciation,
)
from app.services.auth_service import login_required, role_required


def register_asset_management_routes(flask_app):
    @flask_app.route('/asset-categories', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def asset_categories():
        error_message = None
        session = ext.SessionLocal()
        try:
            gl_accounts = session.query(GLAccount).filter(GLAccount.is_active == True).order_by(GLAccount.code).all()
            if request.method == 'POST':
                create_asset_category(**request.form.to_dict())
                return redirect(url_for('asset_categories', success='1'))
            return render_template('asset_categories.html', rows=list_asset_categories(), gl_accounts=gl_accounts, error_message=error_message, success=request.args.get('success'))
        except AssetManagementError as e:
            error_message = str(e)
            gl_accounts = session.query(GLAccount).filter(GLAccount.is_active == True).order_by(GLAccount.code).all()
            return render_template('asset_categories.html', rows=list_asset_categories(), gl_accounts=gl_accounts, error_message=error_message, success=None), 400
        finally:
            session.close()

    @flask_app.route('/asset-locations', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def asset_locations():
        error_message = None
        try:
            if request.method == 'POST':
                create_asset_location(request.form.get('code'), request.form.get('name'), request.form.get('description'))
                return redirect(url_for('asset_locations', success='1'))
            return render_template('asset_locations.html', rows=list_asset_locations(), error_message=error_message, success=request.args.get('success'))
        except AssetManagementError as e:
            return render_template('asset_locations.html', rows=list_asset_locations(), error_message=str(e), success=None), 400

    @flask_app.route('/asset-custodians', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def asset_custodians():
        try:
            if request.method == 'POST':
                create_asset_custodian(request.form.get('full_name'), request.form.get('employee_no'), request.form.get('phone'), request.form.get('email'))
                return redirect(url_for('asset_custodians', success='1'))
            return render_template('asset_custodians.html', rows=list_asset_custodians(), error_message=None, success=request.args.get('success'))
        except AssetManagementError as e:
            return render_template('asset_custodians.html', rows=list_asset_custodians(), error_message=str(e), success=None), 400

    @flask_app.route('/fixed-assets', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def fixed_assets():
        session = ext.SessionLocal(); error_message=None
        try:
            categories = session.query(AssetCategory).filter(AssetCategory.is_active == True).order_by(AssetCategory.code).all()
            locations = session.query(AssetLocation).filter(AssetLocation.is_active == True).order_by(AssetLocation.code).all()
            custodians = session.query(AssetCustodian).filter(AssetCustodian.is_active == True).order_by(AssetCustodian.full_name).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            if request.method == 'POST':
                create_fixed_asset(**request.form.to_dict())
                return redirect(url_for('fixed_assets', success='1'))
            return render_template('fixed_assets.html', rows=list_fixed_assets(), categories=categories, locations=locations, custodians=custodians, branches=branches, default_acquisition_date=date.today().isoformat(), error_message=error_message, success=request.args.get('success'))
        except (AssetManagementError, ValueError) as e:
            categories = session.query(AssetCategory).filter(AssetCategory.is_active == True).order_by(AssetCategory.code).all()
            locations = session.query(AssetLocation).filter(AssetLocation.is_active == True).order_by(AssetLocation.code).all()
            custodians = session.query(AssetCustodian).filter(AssetCustodian.is_active == True).order_by(AssetCustodian.full_name).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            return render_template('fixed_assets.html', rows=list_fixed_assets(), categories=categories, locations=locations, custodians=custodians, branches=branches, default_acquisition_date=date.today().isoformat(), error_message=str(e), success=None), 400
        finally:
            session.close()

    @flask_app.route('/asset-acquisitions', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def asset_acquisitions():
        session = ext.SessionLocal(); error_message=None
        try:
            assets = session.query(FixedAsset).filter(FixedAsset.is_active == True).order_by(FixedAsset.asset_code).all()
            suppliers = session.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name).all()
            cash_accounts = session.query(GLAccount).filter(GLAccount.is_active == True).order_by(GLAccount.code).all()
            if request.method == 'POST':
                current_role=(flask_session.get('role_name') or '').strip().upper()
                auto_post=(request.form.get('action')=='post' and current_role=='ADMIN')
                result=create_asset_acquisition(fixed_asset_id=request.form.get('fixed_asset_id'), acquisition_date=request.form.get('acquisition_date'), supplier_id=request.form.get('supplier_id'), payment_account_id=request.form.get('payment_account_id'), amount=request.form.get('amount'), reference_no=request.form.get('reference_no'), remarks=request.form.get('remarks'), auto_post=auto_post, branch_id=request.form.get('branch_id'))
                return redirect(url_for('asset_acquisitions', success=result['acquisition_no']))
            return render_template('asset_acquisitions.html', rows=list_asset_acquisitions(), assets=assets, suppliers=suppliers, cash_accounts=cash_accounts, default_acquisition_date=date.today().isoformat(), error_message=error_message, success=request.args.get('success'))
        except (AssetManagementError, ValueError) as e:
            assets = session.query(FixedAsset).filter(FixedAsset.is_active == True).order_by(FixedAsset.asset_code).all()
            suppliers = session.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name).all()
            cash_accounts = session.query(GLAccount).filter(GLAccount.is_active == True).order_by(GLAccount.code).all()
            return render_template('asset_acquisitions.html', rows=list_asset_acquisitions(), assets=assets, suppliers=suppliers, cash_accounts=cash_accounts, default_acquisition_date=date.today().isoformat(), error_message=str(e), success=None), 400
        finally: session.close()

    @flask_app.route('/asset-acquisitions/<int:acquisition_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_asset_acquisition_route(acquisition_id):
        try:
            approve_asset_acquisition(acquisition_id)
            return redirect(url_for('asset_acquisitions'))
        except AssetManagementError as e:
            return redirect(url_for('asset_acquisitions', error=str(e)))

    @flask_app.route('/asset-maintenance', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def asset_maintenance():
        session=ext.SessionLocal();
        try:
            assets=session.query(FixedAsset).filter(FixedAsset.is_active == True).order_by(FixedAsset.asset_code).all()
            if request.method=='POST':
                create_asset_maintenance(**request.form.to_dict())
                return redirect(url_for('asset_maintenance', success='1'))
            return render_template('asset_maintenance.html', rows=list_asset_maintenance(), assets=assets, default_maintenance_date=date.today().isoformat(), error_message=None, success=request.args.get('success'))
        except (AssetManagementError, ValueError) as e:
            assets=session.query(FixedAsset).filter(FixedAsset.is_active == True).order_by(FixedAsset.asset_code).all()
            return render_template('asset_maintenance.html', rows=list_asset_maintenance(), assets=assets, default_maintenance_date=date.today().isoformat(), error_message=str(e), success=None), 400
        finally: session.close()

    @flask_app.route('/asset-depreciation', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def asset_depreciation():
        error_message=None
        try:
            if request.method=='POST':
                current_role=(flask_session.get('role_name') or '').strip().upper()
                auto_post=(request.form.get('action')=='post' and current_role=='ADMIN')
                result=run_asset_depreciation(run_date=request.form.get('run_date'), period_label=request.form.get('period_label'), remarks=request.form.get('remarks'), auto_post=auto_post)
                return redirect(url_for('asset_depreciation', success=result['run_no']))
            return render_template('asset_depreciation.html', rows=list_asset_depreciation_runs(), default_run_date=date.today().isoformat(), error_message=error_message, success=request.args.get('success'))
        except AssetManagementError as e:
            return render_template('asset_depreciation.html', rows=list_asset_depreciation_runs(), default_run_date=date.today().isoformat(), error_message=str(e), success=None), 400

    @flask_app.route('/asset-depreciation/<int:run_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_asset_depreciation_route(run_id):
        try:
            approve_asset_depreciation_run(run_id)
            return redirect(url_for('asset_depreciation'))
        except AssetManagementError as e:
            return redirect(url_for('asset_depreciation', error=str(e)))

    @flask_app.route('/asset-disposals', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def asset_disposals():
        session=ext.SessionLocal();
        try:
            assets=session.query(FixedAsset).filter(FixedAsset.is_active == True).order_by(FixedAsset.asset_code).all()
            if request.method=='POST':
                current_role=(flask_session.get('role_name') or '').strip().upper()
                auto_post=(request.form.get('action')=='post' and current_role=='ADMIN')
                result=create_asset_disposal(fixed_asset_id=request.form.get('fixed_asset_id'), disposal_date=request.form.get('disposal_date'), proceeds=request.form.get('proceeds'), disposal_cost=request.form.get('disposal_cost'), remarks=request.form.get('remarks'), auto_post=auto_post)
                return redirect(url_for('asset_disposals', success=result['disposal_no']))
            return render_template('asset_disposals.html', rows=list_asset_disposals(), assets=assets, default_disposal_date=date.today().isoformat(), error_message=None, success=request.args.get('success'))
        except (AssetManagementError, ValueError) as e:
            assets=session.query(FixedAsset).filter(FixedAsset.is_active == True).order_by(FixedAsset.asset_code).all()
            return render_template('asset_disposals.html', rows=list_asset_disposals(), assets=assets, default_disposal_date=date.today().isoformat(), error_message=str(e), success=None), 400
        finally: session.close()

    @flask_app.route('/asset-disposals/<int:disposal_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_asset_disposal_route(disposal_id):
        try:
            approve_asset_disposal(disposal_id)
            return redirect(url_for('asset_disposals'))
        except AssetManagementError as e:
            return redirect(url_for('asset_disposals', error=str(e)))

    @flask_app.route('/asset-reports')
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT', 'MANAGER', 'AUDITOR')
    def asset_reports():
        summary = asset_report_summary()
        return render_template('asset_reports.html', summary=summary)
