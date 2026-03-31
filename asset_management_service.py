from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import app.extensions as ext
from app.models.asset_acquisition import AssetAcquisition
from app.models.asset_category import AssetCategory
from app.models.asset_custodian import AssetCustodian
from app.models.asset_depreciation_line import AssetDepreciationLine
from app.models.asset_depreciation_run import AssetDepreciationRun
from app.models.asset_disposal import AssetDisposal
from app.models.asset_location import AssetLocation
from app.models.asset_maintenance import AssetMaintenance
from app.models.fixed_asset import FixedAsset
from app.services.journal_service import create_journal_draft, post_journal


class AssetManagementError(Exception):
    pass


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError('Database session factory is not initialized.')
    return ext.SessionLocal()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def to_decimal(value: Any) -> Decimal:
    try:
        if value in (None, ''):
            return Decimal('0.00')
        return Decimal(str(value).replace(',', '').strip()).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AssetManagementError('Amount lazima iwe namba sahihi.') from exc


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip(), '%Y-%m-%d').date()
    raise AssetManagementError('Tarehe si sahihi.')


def _next_no(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def list_asset_categories():
    s = _new_session()
    try:
        return s.query(AssetCategory).order_by(AssetCategory.code).all()
    finally:
        s.close()


def create_asset_category(**kwargs):
    s = _new_session()
    try:
        row = AssetCategory(
            code=str(kwargs.get('code') or '').strip().upper(),
            name=str(kwargs.get('name') or '').strip(),
            depreciation_method=str(kwargs.get('depreciation_method') or 'STRAIGHT_LINE').strip().upper(),
            useful_life_months=int(kwargs.get('useful_life_months') or 60),
            gl_asset_account_id=int(kwargs['gl_asset_account_id']) if kwargs.get('gl_asset_account_id') else None,
            gl_accumulated_depreciation_account_id=int(kwargs['gl_accumulated_depreciation_account_id']) if kwargs.get('gl_accumulated_depreciation_account_id') else None,
            gl_depreciation_expense_account_id=int(kwargs['gl_depreciation_expense_account_id']) if kwargs.get('gl_depreciation_expense_account_id') else None,
            gl_disposal_gain_account_id=int(kwargs['gl_disposal_gain_account_id']) if kwargs.get('gl_disposal_gain_account_id') else None,
            gl_disposal_loss_account_id=int(kwargs['gl_disposal_loss_account_id']) if kwargs.get('gl_disposal_loss_account_id') else None,
        )
        if not row.code or not row.name:
            raise AssetManagementError('Code na Name vinahitajika.')
        s.add(row)
        s.commit()
        return row
    except Exception:
        s.rollback(); raise
    finally:
        s.close()


def list_asset_locations():
    s=_new_session();
    try: return s.query(AssetLocation).order_by(AssetLocation.code).all()
    finally: s.close()


def create_asset_location(code, name, description=None):
    s=_new_session();
    try:
        row=AssetLocation(code=str(code).strip().upper(), name=str(name).strip(), description=_clean_text(description))
        if not row.code or not row.name: raise AssetManagementError('Code na Name vinahitajika.')
        s.add(row); s.commit(); return row
    except Exception:
        s.rollback(); raise
    finally: s.close()


def list_asset_custodians():
    s=_new_session();
    try: return s.query(AssetCustodian).order_by(AssetCustodian.full_name).all()
    finally: s.close()


def create_asset_custodian(full_name, employee_no=None, phone=None, email=None):
    s=_new_session();
    try:
        row=AssetCustodian(full_name=str(full_name).strip(), employee_no=_clean_text(employee_no), phone=_clean_text(phone), email=_clean_text(email))
        if not row.full_name: raise AssetManagementError('Full name inahitajika.')
        s.add(row); s.commit(); return row
    except Exception:
        s.rollback(); raise
    finally: s.close()


def list_fixed_assets():
    s=_new_session()
    try:
        return s.query(FixedAsset).order_by(FixedAsset.asset_code).all()
    finally:
        s.close()


def create_fixed_asset(**kwargs):
    s=_new_session()
    try:
        cost = to_decimal(kwargs.get('cost'))
        salvage = to_decimal(kwargs.get('salvage_value'))
        row=FixedAsset(
            asset_code=str(kwargs.get('asset_code') or '').strip().upper(),
            asset_name=str(kwargs.get('asset_name') or '').strip(),
            category_id=int(kwargs.get('category_id')),
            branch_id=int(kwargs['branch_id']) if kwargs.get('branch_id') else None,
            location_id=int(kwargs['location_id']) if kwargs.get('location_id') else None,
            custodian_id=int(kwargs['custodian_id']) if kwargs.get('custodian_id') else None,
            acquisition_date=_parse_date(kwargs.get('acquisition_date')),
            capitalization_date=_parse_date(kwargs.get('capitalization_date') or kwargs.get('acquisition_date')),
            cost=cost,
            salvage_value=salvage,
            useful_life_months=int(kwargs.get('useful_life_months') or 60),
            depreciation_method=str(kwargs.get('depreciation_method') or 'STRAIGHT_LINE').strip().upper(),
            accumulated_depreciation=Decimal('0.00'),
            carrying_amount=cost,
            funding_source=_clean_text(kwargs.get('funding_source')),
            description=_clean_text(kwargs.get('description')),
        )
        if not row.asset_code or not row.asset_name:
            raise AssetManagementError('Asset Code na Asset Name vinahitajika.')
        s.add(row); s.commit(); return row
    except Exception:
        s.rollback(); raise
    finally:
        s.close()


def list_asset_acquisitions():
    s=_new_session();
    try: return s.query(AssetAcquisition).order_by(AssetAcquisition.id.desc()).all()
    finally: s.close()


def create_asset_acquisition(*, fixed_asset_id, acquisition_date, supplier_id=None, payment_account_id=None, amount, reference_no=None, remarks=None, auto_post=False, branch_id=None):
    s=_new_session()
    try:
        asset = s.get(FixedAsset, int(fixed_asset_id))
        if not asset: raise AssetManagementError('Asset haipo.')
        amt = to_decimal(amount)
        row=AssetAcquisition(fixed_asset_id=asset.id, acquisition_no=_next_no('AQ'), acquisition_date=_parse_date(acquisition_date), supplier_id=int(supplier_id) if supplier_id else None, payment_account_id=int(payment_account_id) if payment_account_id else None, amount=amt, reference_no=_clean_text(reference_no), remarks=_clean_text(remarks), status='draft')
        s.add(row); s.commit(); acq_id=row.id
    except Exception:
        s.rollback(); raise
    finally:
        s.close()
    if auto_post:
        approve_asset_acquisition(acq_id, branch_id=branch_id or asset.branch_id)
    return {'acquisition_id': acq_id, 'acquisition_no': row.acquisition_no}


def approve_asset_acquisition(acquisition_id: int, branch_id: int | None = None):
    s=_new_session()
    try:
        row=s.get(AssetAcquisition, acquisition_id)
        if not row: raise AssetManagementError('Asset acquisition haipo.')
        asset=s.get(FixedAsset, row.fixed_asset_id)
        category=s.get(AssetCategory, asset.category_id)
        if not category or not category.gl_asset_account_id or not row.payment_account_id:
            raise AssetManagementError('Asset acquisition inahitaji GL mapping kamili.')
        j=create_journal_draft(branch_id=branch_id or asset.branch_id or 1, journal_date=row.acquisition_date, source_module='ASSET_ACQUISITION', reference_no=row.acquisition_no, narration=row.remarks or f'Asset acquisition {row.acquisition_no}', lines=[
            {'gl_account_id': category.gl_asset_account_id, 'description': asset.asset_name, 'debit_amount': row.amount, 'credit_amount': Decimal('0.00')},
            {'gl_account_id': row.payment_account_id, 'description': asset.asset_name, 'debit_amount': Decimal('0.00'), 'credit_amount': row.amount},
        ])
        post_journal(j)
        row.journal_batch_id=j; row.status='posted'; s.commit(); return row
    except Exception:
        s.rollback(); raise
    finally: s.close()


def list_asset_maintenance():
    s=_new_session();
    try: return s.query(AssetMaintenance).order_by(AssetMaintenance.id.desc()).all()
    finally: s.close()


def create_asset_maintenance(**kwargs):
    s=_new_session();
    try:
        row=AssetMaintenance(fixed_asset_id=int(kwargs.get('fixed_asset_id')), maintenance_date=_parse_date(kwargs.get('maintenance_date')), maintenance_type=str(kwargs.get('maintenance_type') or '').strip(), service_provider=_clean_text(kwargs.get('service_provider')), cost=to_decimal(kwargs.get('cost')), remarks=_clean_text(kwargs.get('remarks')), status='draft')
        if not row.maintenance_type: raise AssetManagementError('Maintenance type inahitajika.')
        s.add(row); s.commit(); return row
    except Exception:
        s.rollback(); raise
    finally: s.close()


def list_asset_depreciation_runs():
    s=_new_session();
    try: return s.query(AssetDepreciationRun).order_by(AssetDepreciationRun.id.desc()).all()
    finally: s.close()


def run_asset_depreciation(*, run_date, period_label, remarks=None, auto_post=False, branch_id=None):
    s=_new_session()
    try:
        rd=_parse_date(run_date)
        run=AssetDepreciationRun(run_no=_next_no('DEP'), run_date=rd, period_label=str(period_label).strip(), remarks=_clean_text(remarks), status='draft')
        s.add(run); s.flush()
        total=Decimal('0.00')
        assets=s.query(FixedAsset).filter(FixedAsset.status=='active').all()
        for asset in assets:
            depreciable = max(Decimal(asset.cost) - Decimal(asset.salvage_value) - Decimal(asset.accumulated_depreciation), Decimal('0.00'))
            if depreciable <= 0 or int(asset.useful_life_months or 0) <= 0:
                continue
            monthly = (Decimal(asset.cost) - Decimal(asset.salvage_value)) / Decimal(asset.useful_life_months)
            amount = monthly.quantize(Decimal('0.01'))
            if amount <= 0:
                continue
            s.add(AssetDepreciationLine(run_id=run.id, fixed_asset_id=asset.id, depreciation_amount=amount))
            asset.accumulated_depreciation = Decimal(asset.accumulated_depreciation) + amount
            asset.carrying_amount = max(Decimal(asset.cost) - Decimal(asset.accumulated_depreciation), Decimal('0.00'))
            total += amount
        s.commit(); run_id=run.id
    except Exception:
        s.rollback(); raise
    finally: s.close()
    if auto_post:
        approve_asset_depreciation_run(run_id, branch_id=branch_id)
    return {'run_id': run_id, 'run_no': run.run_no, 'total_amount': str(total)}


def approve_asset_depreciation_run(run_id: int, branch_id: int | None = None):
    s=_new_session()
    try:
        run=s.get(AssetDepreciationRun, run_id)
        if not run: raise AssetManagementError('Depreciation run haipo.')
        lines=s.query(AssetDepreciationLine).filter_by(run_id=run.id).all()
        if not lines: raise AssetManagementError('Hakuna depreciation lines.')
        grouped={}
        branch = branch_id or 1
        for line in lines:
            asset=s.get(FixedAsset, line.fixed_asset_id)
            category=s.get(AssetCategory, asset.category_id)
            if not category or not category.gl_depreciation_expense_account_id or not category.gl_accumulated_depreciation_account_id:
                raise AssetManagementError('Depreciation GL mapping haijakamilika.')
            grouped.setdefault((category.gl_depreciation_expense_account_id, 'dr'), Decimal('0.00'))
            grouped[(category.gl_depreciation_expense_account_id, 'dr')] += Decimal(line.depreciation_amount)
            grouped.setdefault((category.gl_accumulated_depreciation_account_id, 'cr'), Decimal('0.00'))
            grouped[(category.gl_accumulated_depreciation_account_id, 'cr')] += Decimal(line.depreciation_amount)
            branch = asset.branch_id or branch
        journal_lines=[]
        for (acc, side), amount in grouped.items():
            journal_lines.append({'gl_account_id': acc, 'description': f'Depreciation {run.period_label}', 'debit_amount': amount if side=='dr' else Decimal('0.00'), 'credit_amount': amount if side=='cr' else Decimal('0.00')})
        j=create_journal_draft(branch_id=branch, journal_date=run.run_date, source_module='ASSET_DEPRECIATION', reference_no=run.run_no, narration=run.remarks or f'Asset depreciation {run.period_label}', lines=journal_lines)
        post_journal(j)
        run.journal_batch_id=j; run.status='posted'; s.commit(); return run
    except Exception:
        s.rollback(); raise
    finally: s.close()


def list_asset_disposals():
    s=_new_session();
    try: return s.query(AssetDisposal).order_by(AssetDisposal.id.desc()).all()
    finally: s.close()


def create_asset_disposal(*, fixed_asset_id, disposal_date, proceeds, disposal_cost=0, remarks=None, auto_post=False, branch_id=None):
    s=_new_session();
    try:
        asset=s.get(FixedAsset, int(fixed_asset_id))
        if not asset: raise AssetManagementError('Asset haipo.')
        row=AssetDisposal(fixed_asset_id=asset.id, disposal_no=_next_no('DSP'), disposal_date=_parse_date(disposal_date), proceeds=to_decimal(proceeds), disposal_cost=to_decimal(disposal_cost), remarks=_clean_text(remarks), status='draft')
        s.add(row); s.commit(); disposal_id=row.id
    except Exception:
        s.rollback(); raise
    finally: s.close()
    if auto_post:
        approve_asset_disposal(disposal_id, branch_id=branch_id or asset.branch_id)
    return {'disposal_id': disposal_id, 'disposal_no': row.disposal_no}


def approve_asset_disposal(disposal_id: int, branch_id: int | None = None):
    s=_new_session();
    try:
        row=s.get(AssetDisposal, disposal_id)
        if not row: raise AssetManagementError('Asset disposal haipo.')
        asset=s.get(FixedAsset, row.fixed_asset_id)
        category=s.get(AssetCategory, asset.category_id)
        if not category or not category.gl_asset_account_id or not category.gl_accumulated_depreciation_account_id:
            raise AssetManagementError('Disposal GL mapping haijakamilika.')
        nbv=max(Decimal(asset.cost)-Decimal(asset.accumulated_depreciation), Decimal('0.00'))
        result=(Decimal(row.proceeds)-Decimal(row.disposal_cost))-nbv
        gain_acc=category.gl_disposal_gain_account_id
        loss_acc=category.gl_disposal_loss_account_id
        lines=[
            {'gl_account_id': category.gl_accumulated_depreciation_account_id, 'description': asset.asset_name, 'debit_amount': Decimal(asset.accumulated_depreciation), 'credit_amount': Decimal('0.00')},
            {'gl_account_id': category.gl_asset_account_id, 'description': asset.asset_name, 'debit_amount': Decimal('0.00'), 'credit_amount': Decimal(asset.cost)},
        ]
        # optional proceeds ignored if no cash mapping supplied; user can record separate receipt
        if result > 0 and gain_acc:
            lines.append({'gl_account_id': gain_acc, 'description': f'Gain on disposal {row.disposal_no}', 'debit_amount': Decimal('0.00'), 'credit_amount': result})
        elif result < 0 and loss_acc:
            lines.append({'gl_account_id': loss_acc, 'description': f'Loss on disposal {row.disposal_no}', 'debit_amount': abs(result), 'credit_amount': Decimal('0.00')})
        j=create_journal_draft(branch_id=branch_id or asset.branch_id or 1, journal_date=row.disposal_date, source_module='ASSET_DISPOSAL', reference_no=row.disposal_no, narration=row.remarks or f'Asset disposal {row.disposal_no}', lines=lines)
        post_journal(j)
        row.journal_batch_id=j; row.status='posted'; asset.status='disposed'; asset.is_active=False; s.commit(); return row
    except Exception:
        s.rollback(); raise
    finally: s.close()


def asset_report_summary():
    s=_new_session()
    try:
        assets=s.query(FixedAsset).all()
        total_cost=sum((Decimal(a.cost) for a in assets), Decimal('0.00'))
        total_acc_dep=sum((Decimal(a.accumulated_depreciation) for a in assets), Decimal('0.00'))
        total_carry=sum((Decimal(a.carrying_amount) for a in assets), Decimal('0.00'))
        active_count=sum(1 for a in assets if a.status == 'active')
        disposed_count=sum(1 for a in assets if a.status == 'disposed')
        return {'assets': assets, 'total_cost': total_cost, 'total_accumulated_depreciation': total_acc_dep, 'total_carrying_amount': total_carry, 'active_count': active_count, 'disposed_count': disposed_count}
    finally:
        s.close()
