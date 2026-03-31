from importlib import import_module

from app import create_app
import app.extensions as ext


def pick_class(module_path: str, candidates: list[str]):
    module = import_module(module_path)
    for name in candidates:
        if hasattr(module, name):
            return getattr(module, name)
    raise ImportError(
        f"Could not find any of {candidates} in {module_path}"
    )


NHIFClaimBatchModel = pick_class(
    "app.models.nhif_claim_batch",
    ["NHIFClaimBatch", "NhifClaimBatch", "NhifClaimbatch"],
)

NHIFClaimModel = pick_class(
    "app.models.nhif_claim",
    ["NHIFClaim", "NhifClaim"],
)

NHIFCollectionModel = pick_class(
    "app.models.nhif_collection",
    ["NHIFCollection", "NhifCollection"],
)

NHIFRejectionModel = pick_class(
    "app.models.nhif_rejection",
    ["NHIFRejection", "NhifRejection"],
)

app = create_app()

with app.app_context():
    engine = ext.get_engine()

    NHIFClaimBatchModel.__table__.create(bind=engine, checkfirst=True)
    NHIFClaimModel.__table__.create(bind=engine, checkfirst=True)
    NHIFCollectionModel.__table__.create(bind=engine, checkfirst=True)
    NHIFRejectionModel.__table__.create(bind=engine, checkfirst=True)

    print("NHIF tables created/verified successfully.")