# NHIF Import + Posting + Reconciliation Full Pack

This pack is additive and extends your NHIF module with:
1. PDF import/upload
2. Claim capture and import parsing
3. Collections capture
4. Rejections / losses capture
5. Reconciliation and dashboard views
6. TZS currency formatting in templates

## Manual integration
1. Add model imports in `app/models/__init__.py`:
```python
from .nhif_import_batch import NHIFImportBatch
from .nhif_claim_batch import NHIFClaimBatch
from .nhif_claim import NHIFClaim
from .nhif_collection import NHIFCollection
from .nhif_rejection import NHIFRejection
```

2. Register NHIF routes in `app/__init__.py`:
```python
from app.nhif_routes import register_nhif_routes
...
register_nhif_routes(flask_app)
```

3. If needed, install PDF reader:
```powershell
pip install pypdf
```

4. Sidebar links:
- /nhif-import
- /nhif-claims
- /nhif-collections
- /nhif-rejections
- /nhif-reconciliation
- /nhif-dashboard
