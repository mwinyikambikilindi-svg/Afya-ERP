from app import create_app
import app.extensions as ext
from sqlalchemy import text

app = create_app()

TARGET_COLUMNS = [
    ("batch_id", "INTEGER"),
    ("gross_amount", "NUMERIC(18,2)"),
    ("net_amount", "NUMERIC(18,2)"),
    ("approved_amount", "NUMERIC(18,2)"),
    ("rejected_amount", "NUMERIC(18,2)"),
    ("deduction_amount", "NUMERIC(18,2)"),
    ("amount_claimed", "NUMERIC(18,2)"),
    ("amount_paid", "NUMERIC(18,2)"),
    ("claim_forms_count", "INTEGER"),
    ("payment_reference", "VARCHAR(120)"),
    ("facility_name", "VARCHAR(255)"),
    ("claim_month", "VARCHAR(40)"),
    ("nhif_reference", "VARCHAR(120)"),
    ("status", "VARCHAR(30)"),
    ("import_batch_id", "INTEGER"),
]

with app.app_context():
    engine = ext.get_engine()

    with engine.begin() as conn:
        # Ensure columns exist
        existing = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'nhif_claims'
        """)).fetchall()
        existing_cols = {r[0] for r in existing}

        for col_name, col_type in TARGET_COLUMNS:
            if col_name not in existing_cols:
                conn.execute(text(f'ALTER TABLE nhif_claims ADD COLUMN "{col_name}" {col_type};'))

        # Relax legacy NOT NULL constraints
        for col_name, _ in TARGET_COLUMNS:
            conn.execute(text(f'ALTER TABLE nhif_claims ALTER COLUMN "{col_name}" DROP NOT NULL;'))

        # Safe defaults for numeric columns
        for num_col in [
            "gross_amount",
            "net_amount",
            "approved_amount",
            "rejected_amount",
            "deduction_amount",
            "amount_claimed",
            "amount_paid",
        ]:
            conn.execute(text(f'ALTER TABLE nhif_claims ALTER COLUMN "{num_col}" SET DEFAULT 0;'))

        conn.execute(text('ALTER TABLE nhif_claims ALTER COLUMN "status" SET DEFAULT \'draft\';'))

        # Backfill null numerics to zero
        conn.execute(text("""
            UPDATE nhif_claims
            SET
                gross_amount = COALESCE(gross_amount, 0),
                net_amount = COALESCE(net_amount, 0),
                approved_amount = COALESCE(approved_amount, 0),
                rejected_amount = COALESCE(rejected_amount, 0),
                deduction_amount = COALESCE(deduction_amount, 0),
                amount_claimed = COALESCE(amount_claimed, gross_amount, 0),
                amount_paid = COALESCE(amount_paid, approved_amount, net_amount, 0),
                status = COALESCE(status, 'draft')
        """))

    print("NHIF claims schema normalized successfully.")