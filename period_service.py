from calendar import monthrange
from datetime import datetime, date, timedelta

import app.extensions as ext
from app.models.fiscal_year import FiscalYear
from app.models.accounting_period import AccountingPeriod


class PeriodServiceError(Exception):
    pass


def _to_date(value):
    if isinstance(value, str):
        value = value.strip()
        return datetime.strptime(value, "%Y-%m-%d").date()
    return value


def _month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def create_fiscal_year_with_periods(year_name: str, start_date, end_date):
    start_date = _to_date(start_date)
    end_date = _to_date(end_date)

    if not year_name.strip():
        raise PeriodServiceError("Weka year name.")

    if start_date > end_date:
        raise PeriodServiceError("Start date haiwezi kuwa kubwa kuliko end date.")

    session = ext.SessionLocal()

    try:
        existing_name = (
            session.query(FiscalYear)
            .filter(FiscalYear.year_name == year_name.strip())
            .first()
        )
        if existing_name:
            raise PeriodServiceError("Fiscal year name tayari ipo.")

        overlap = (
            session.query(FiscalYear)
            .filter(
                FiscalYear.start_date <= end_date,
                FiscalYear.end_date >= start_date,
            )
            .first()
        )
        if overlap:
            raise PeriodServiceError("Hii fiscal year ina-overlap na fiscal year nyingine iliyopo.")

        fy = FiscalYear(
            year_name=year_name.strip(),
            start_date=start_date,
            end_date=end_date,
            status="open",
        )
        session.add(fy)
        session.flush()

        period_no = 1
        cursor = start_date

        while cursor <= end_date:
            period_start = cursor
            period_end = min(_month_end(cursor), end_date)
            period_name = period_start.strftime("%b %Y")

            period = AccountingPeriod(
                fiscal_year_id=fy.id,
                period_no=period_no,
                period_name=period_name,
                start_date=period_start,
                end_date=period_end,
                status="open",
            )
            session.add(period)

            cursor = period_end + timedelta(days=1)
            period_no += 1

        session.commit()
        return fy.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_accounting_periods():
    session = ext.SessionLocal()

    try:
        rows = (
            session.query(AccountingPeriod, FiscalYear)
            .join(FiscalYear, FiscalYear.id == AccountingPeriod.fiscal_year_id)
            .order_by(AccountingPeriod.start_date.desc(), AccountingPeriod.id.desc())
            .all()
        )

        result = []
        for period, fy in rows:
            result.append(
                {
                    "id": period.id,
                    "fiscal_year_id": fy.id,
                    "year_name": fy.year_name,
                    "period_no": period.period_no,
                    "period_name": period.period_name,
                    "start_date": period.start_date,
                    "end_date": period.end_date,
                    "status": period.status,
                }
            )

        return result

    finally:
        session.close()


def change_period_status(period_id: int, new_status: str):
    if new_status not in ("open", "closed"):
        raise PeriodServiceError("Status ya period si sahihi.")

    session = ext.SessionLocal()

    try:
        period = session.get(AccountingPeriod, period_id)
        if not period:
            raise PeriodServiceError("Accounting period haipo.")

        period.status = new_status
        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()