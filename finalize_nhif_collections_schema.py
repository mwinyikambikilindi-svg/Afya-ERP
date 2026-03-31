from app import create_app
import app.extensions as ext
from sqlalchemy import text

app = create_app()

with app.app_context():
    engine = ext.get_engine()

    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'nhif_collections'
            ORDER BY ordinal_position
        """)).fetchall()

        cols = [r[0] for r in rows]
        protected = {"id"}

        for col in cols:
            if col not in protected:
                conn.execute(text(f'ALTER TABLE nhif_collections ALTER COLUMN "{col}" DROP NOT NULL;'))

        numeric_defaults = [
            "amount",
            "amount_collected",
        ]
        for col in numeric_defaults:
            if col in cols:
                conn.execute(text(f'ALTER TABLE nhif_collections ALTER COLUMN "{col}" SET DEFAULT 0;'))

        date_fill_columns = ["collection_date", "receipt_date", "bank_date", "deposit_date"]
        for col in date_fill_columns:
            if col in cols:
                conn.execute(text(f'''
                    UPDATE nhif_collections
                    SET "{col}" = COALESCE("{col}", CURRENT_DATE)
                '''))

        text_fill_columns = ["receipt_no", "receipt_reference", "reference_no", "payment_reference", "bank_reference"]
        for col in text_fill_columns:
            if col in cols:
                conn.execute(text(f'''
                    UPDATE nhif_collections
                    SET "{col}" = COALESCE("{col}", 'AUTO-FILL')
                '''))

        if "amount" in cols:
            conn.execute(text('UPDATE nhif_collections SET "amount" = COALESCE("amount", 0)'))
        if "amount_collected" in cols:
            conn.execute(text('UPDATE nhif_collections SET "amount_collected" = COALESCE("amount_collected", 0)'))

    print("NHIF collections schema finalized successfully.")