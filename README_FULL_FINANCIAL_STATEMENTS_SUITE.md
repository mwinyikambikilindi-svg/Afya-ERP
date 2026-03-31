# Full Financial Statements Suite Pack

This pack upgrades the report engine from a starter pack into a fuller suite aligned to PMU statement flow:

1. Statement of Financial Position
2. Statement of Financial Performance
3. Statement of Changes in Net Assets / Equity
4. Cash Flow Statement
5. Notes landing page
6. Trial Balance

## Important
- This pack preserves GL as posting truth and GFS as reporting truth.
- It is designed to co-exist with old routes already in the system.
- New routes are namespaced under `/reports/...` to avoid colliding with legacy routes like `/trial-balance`.

## Included
- enhanced reporting service
- full report routes
- templates for:
  - SOFP
  - SOFPERF
  - Changes in Equity
  - Cash Flow
  - Notes index
  - Trial Balance
- sidebar/menu snippet
- integration notes for app init
