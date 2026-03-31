# GFS Table Design + Seed Pack

This pack creates:
1. `gfs_codes` live table
2. `gl_account_gfs_map` mapping table
3. PMU smart starter GFS seed CSV
4. Mapping plan notes for GL -> GFS

## Why this structure
Your live DB already has `account_classes`, `account_groups`, and `gl_accounts`, which form the posting engine.
This GFS layer is a reporting / public-sector classification layer, not a replacement for the chart of accounts.

## Seed logic basis
The starter seed aligns to PMU financial statement lines such as:
- Cash and Cash Equivalents
- Receivables
- Inventories
- PPE
- Payables and Accruals
- Taxpayer's Fund
- Revenue Grants
- Other Revenue
- Revenue from User Contribution
- Wages, Salaries and Employee Benefits
- Use of Goods and Services
- Maintenance Expenses
- Depreciation
- Other Expenses
- Expected Credit Loss
