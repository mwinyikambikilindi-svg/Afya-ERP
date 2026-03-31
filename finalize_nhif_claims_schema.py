from app import create_app
import app.extensions as ext
from sqlalchemy import text

app = create_app()

with app.app_context():
    engine = ext.get_engine()

    with engine.begin() as conn:
        # columns zote za nhif_claims
        rows = conn.execute(text("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'nhif_claims'
            ORDER BY ordinal_position
        """)).fetchall()

        cols = [r[0] for r in rows]

        # usiguse primary key id tu
        protected = {"id"}

        # drop NOT NULL kwa columns zote nyingine
        for col in cols:
            if col not in protected:
                conn.execute(text(f'ALTER TABLE nhif_claims ALTER COLUMN "{col}" DROP NOT NULL;'))

        # defaults za numeric/common legacy fields
        numeric_defaults = [
            "gross_amount",
            "net_amount",
            "approved_amount",
            "adjusted_amount",
            "rejected_amount",
            "deduction_amount",
            "amount_claimed",
            "amount_paid",
        ]
        for col in numeric_defaults:
            if col in cols:
                conn.execute(text(f'ALTER TABLE nhif_claims ALTER COLUMN "{col}" SET DEFAULT 0;'))

        text_defaults = {
            "status": "draft",
            "adjudication_status": "pending",
        }
        for col, default_val in text_defaults.items():
            if col in cols:
                conn.execute(text(f"ALTER TABLE nhif_claims ALTER COLUMN \"{col}\" SET DEFAULT '{default_val}';"))

        # backfill nulls
        if "status" in cols:
            conn.execute(text("UPDATE nhif_claims SET status = COALESCE(status, 'draft');"))

        if "adjudication_status" in cols:
            conn.execute(text("UPDATE nhif_claims SET adjudication_status = COALESCE(adjudication_status, 'pending');"))

        for col in numeric_defaults:
            if col in cols:
                conn.execute(text(f'UPDATE nhif_claims SET "{col}" = COALESCE("{col}", 0);'))

    print("NHIF claims schema finalized successfully.")