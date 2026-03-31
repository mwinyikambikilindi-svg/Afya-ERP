from app import create_app
import app.extensions as ext
from sqlalchemy import text
import csv
from pathlib import Path

app = create_app()

CSV_PATH = Path("gl_gfs_mapping_output/gl_gfs_candidates.csv")

with app.app_context():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH.resolve()}")

    s = ext.SessionLocal()
    try:
        with CSV_PATH.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                s.execute(
                    text("""
                        INSERT INTO gl_gfs_mapping_review
                        (
                            gl_account_id,
                            gl_account_code,
                            gl_account_name,
                            account_type,
                            suggested_gfs_code,
                            suggested_gfs_name,
                            confidence,
                            mapping_basis,
                            review_status,
                            reviewer_note
                        )
                        VALUES
                        (
                            :gl_account_id,
                            :gl_account_code,
                            :gl_account_name,
                            :account_type,
                            :suggested_gfs_code,
                            :suggested_gfs_name,
                            :confidence,
                            :mapping_basis,
                            :review_status,
                            :reviewer_note
                        )
                    """),
                    {
                        "gl_account_id": int(row["gl_account_id"]) if row["gl_account_id"] else None,
                        "gl_account_code": row["gl_account_code"],
                        "gl_account_name": row["gl_account_name"],
                        "account_type": row["account_type"],
                        "suggested_gfs_code": row["suggested_gfs_code"],
                        "suggested_gfs_name": row["suggested_gfs_name"],
                        "confidence": row["confidence"],
                        "mapping_basis": row["mapping_basis"],
                        "review_status": row["review_status"] or "pending",
                        "reviewer_note": row["reviewer_note"],
                    }
                )

        s.commit()
        print("GL -> GFS candidates imported into gl_gfs_mapping_review successfully.")
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()