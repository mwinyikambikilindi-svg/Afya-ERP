# Financial Statement Accuracy + Comparative Columns Pack

This pack upgrades the financial statements suite with:
- current year vs previous year comparative columns
- stronger section ordering
- section subtotal logic
- PMU-style label discipline
- reusable service methods for year-based comparative statements

## Included
- enhanced reporting service
- report routes with comparative support
- templates for:
  - SOFP with current/prior year columns
  - SOFPERF with current/prior year columns
  - Trial Balance with period filters
  - Changes in Equity with current/prior perspective
  - Cash Flow with current/prior perspective

## Integration
Replace:
- app/services/reporting_service.py
- app/report_routes.py
- relevant templates in app/templates/reports/

## Notes
This pack assumes:
- fiscal_years table exists
- journal_batches can be filtered by fiscal_year_id
- gl_account_gfs_map is already populated
