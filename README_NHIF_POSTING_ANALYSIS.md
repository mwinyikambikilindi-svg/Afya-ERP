# NHIF Posting + Rejection Analysis Full Pack

This pack extends the current NHIF module with:
1. Posting-ready accounting logic
2. Claim -> Receivable recognition rules
3. Collection -> Bank / NHIF Receivable logic
4. Rejection/Loss -> Loss on User Contribution NHIF logic
5. Rejection reason analysis
6. Improved reconciliation and dashboard analytics
7. Consistent TZS currency display

## IMPORTANT
This pack is additive and designed to fit your existing NHIF module.
It does NOT replace the shell UI.

## Manual integration steps
1. Replace/add:
   - app/services/nhif_posting_service.py
   - app/services/nhif_service.py
   - app/nhif_routes.py
   - app/templates/nhif_claims.html
   - app/templates/nhif_collections.html
   - app/templates/nhif_rejections.html
   - app/templates/nhif_reconciliation.html
   - app/templates/nhif_dashboard.html

2. Ensure NHIF routes are registered in app/__init__.py:
```python
from app.nhif_routes import register_nhif_routes
...
register_nhif_routes(flask_app)
```

3. Ensure these GL titles exist in your chart / mapping:
- Receivable from NHIF
- User Contribution NHIF
- Loss on User Contribution NHIF
- Bank Balance

4. This pack does not auto-post journals blindly. It prepares posting-ready records and dashboard logic.
   If you want strict GL journal integration to journal_batches/journal_lines, that can be added as the next pass.

## Business posting intent
- Claim recognized:
  Dr NHIF Receivable
  Cr User Contribution NHIF

- Collection received:
  Dr Bank
  Cr NHIF Receivable

- Rejection/Loss confirmed:
  Dr Loss on User Contribution NHIF
  Cr NHIF Receivable
