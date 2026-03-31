# GL Accounts to GFS Mapping Pack

This pack helps you start mapping live `gl_accounts` into the new `gfs_codes` layer.

## What is inside
1. SQL to create a review table for mappings
2. Python script to extract live GL accounts and propose GFS candidates by keyword heuristics
3. Mapping review CSV template
4. Notes on how to validate and finalize mappings

## Recommended flow
1. Run your GFS create + seed SQL first
2. Run `001_create_gl_gfs_review_table.sql`
3. Run `generate_gl_gfs_candidates.py`
4. Review the generated CSV
5. Import/finalize approved mappings into `gl_account_gfs_map`

## Important principle
- GL Accounts = posting truth
- GFS Codes = reporting truth
- Do not auto-post permanent mappings without review
