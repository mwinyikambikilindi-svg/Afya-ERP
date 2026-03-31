from app import create_app
import app.extensions as ext
from sqlalchemy import text

app = create_app()

SQL_STATEMENTS = [
    # -----------------------------
    # NHIF CLAIMS
    # -----------------------------
    """
    CREATE TABLE IF NOT EXISTS nhif_claims (
        id SERIAL PRIMARY KEY,
        facility_name VARCHAR(255),
        claim_month VARCHAR(40),
        nhif_reference VARCHAR(120),
        claim_date DATE,
        amount_claimed NUMERIC(18,2) DEFAULT 0,
        amount_paid NUMERIC(18,2) DEFAULT 0,
        claim_forms_count INTEGER,
        payment_reference VARCHAR(120),
        import_batch_id INTEGER,
        status VARCHAR(30) DEFAULT 'draft'
    );
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS facility_name VARCHAR(255);
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS claim_month VARCHAR(40);
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS nhif_reference VARCHAR(120);
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS claim_date DATE;
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS amount_claimed NUMERIC(18,2) DEFAULT 0;
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS amount_paid NUMERIC(18,2) DEFAULT 0;
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS claim_forms_count INTEGER;
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(120);
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS import_batch_id INTEGER;
    """,
    """
    ALTER TABLE nhif_claims ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'draft';
    """,

    # -----------------------------
    # NHIF COLLECTIONS
    # -----------------------------
    """
    CREATE TABLE IF NOT EXISTS nhif_collections (
        id SERIAL PRIMARY KEY,
        claim_id INTEGER,
        collection_date DATE,
        amount_collected NUMERIC(18,2) DEFAULT 0,
        receipt_reference VARCHAR(120),
        bank_reference VARCHAR(120)
    );
    """,
    """
    ALTER TABLE nhif_collections ADD COLUMN IF NOT EXISTS claim_id INTEGER;
    """,
    """
    ALTER TABLE nhif_collections ADD COLUMN IF NOT EXISTS collection_date DATE;
    """,
    """
    ALTER TABLE nhif_collections ADD COLUMN IF NOT EXISTS amount_collected NUMERIC(18,2) DEFAULT 0;
    """,
    """
    ALTER TABLE nhif_collections ADD COLUMN IF NOT EXISTS receipt_reference VARCHAR(120);
    """,
    """
    ALTER TABLE nhif_collections ADD COLUMN IF NOT EXISTS bank_reference VARCHAR(120);
    """,

    # -----------------------------
    # NHIF REJECTIONS
    # -----------------------------
    """
    CREATE TABLE IF NOT EXISTS nhif_rejections (
        id SERIAL PRIMARY KEY,
        claim_id INTEGER,
        rejection_date DATE,
        rejection_reason TEXT,
        amount_rejected NUMERIC(18,2) DEFAULT 0
    );
    """,
    """
    ALTER TABLE nhif_rejections ADD COLUMN IF NOT EXISTS claim_id INTEGER;
    """,
    """
    ALTER TABLE nhif_rejections ADD COLUMN IF NOT EXISTS rejection_date DATE;
    """,
    """
    ALTER TABLE nhif_rejections ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
    """,
    """
    ALTER TABLE nhif_rejections ADD COLUMN IF NOT EXISTS amount_rejected NUMERIC(18,2) DEFAULT 0;
    """,

    # -----------------------------
    # NHIF IMPORT BATCHES
    # -----------------------------
    """
    CREATE TABLE IF NOT EXISTS nhif_import_batches (
        id SERIAL PRIMARY KEY,
        facility_name VARCHAR(255),
        source_filename VARCHAR(255) NOT NULL,
        claim_month VARCHAR(40),
        nhif_reference VARCHAR(120),
        imported_by_user_id INTEGER,
        status VARCHAR(30) DEFAULT 'imported',
        raw_text_excerpt TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS facility_name VARCHAR(255);
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS source_filename VARCHAR(255);
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS claim_month VARCHAR(40);
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS nhif_reference VARCHAR(120);
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS imported_by_user_id INTEGER;
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'imported';
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS raw_text_excerpt TEXT;
    """,
    """
    ALTER TABLE nhif_import_batches ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """,
]


with app.app_context():
    engine = ext.get_engine()

    with engine.begin() as conn:
        for stmt in SQL_STATEMENTS:
            conn.execute(text(stmt))

    print("NHIF schema upgrade completed successfully.")