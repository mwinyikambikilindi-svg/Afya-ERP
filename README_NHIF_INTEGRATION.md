NHIF FULL PACK INTEGRATION
==========================

1. Add the new files in this pack to your project.
2. In app/__init__.py register the NHIF routes:

    try:
        from app.nhif_routes import register_nhif_routes
        register_nhif_routes(flask_app)
        flask_app.logger.info("NHIF routes registered.")
    except Exception as e:
        flask_app.logger.warning("NHIF routes not registered: %s", e)

3. In app/models/__init__.py add:
    from .nhif_claim_batch import NHIFClaimBatch
    from .nhif_claim import NHIFClaim
    from .nhif_collection import NHIFCollection
    from .nhif_rejection import NHIFRejection

4. In app/templates/base.html add sidebar menu links:

    <a href="/nhif-claims">NHIF Claims</a>
    <a href="/nhif-collections">NHIF Collections</a>
    <a href="/nhif-rejections">NHIF Rejections / Losses</a>
    <a href="/nhif-reconciliation">NHIF Reconciliation</a>
    <a href="/nhif-dashboard">NHIF Dashboard</a>

5. AUTO_CREATE_TABLES must be 1 only in development if you want the new NHIF tables auto-created.
   For pilot/live, create the tables once in dev, then keep AUTO_CREATE_TABLES=0.
