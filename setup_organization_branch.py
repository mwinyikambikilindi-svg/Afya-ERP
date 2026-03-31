from sqlalchemy import text
from app import create_app
import app.extensions as ext

app = create_app()

# WEKA TAARIFA ZAKO HALISI HAPA
ORG_NAME = "WEKA JINA HALISI LA TAASISI YAKO"
ORG_SHORT_NAME = "WEKA SHORT NAME"
ORG_TIN = "WEKA TIN KAMA IPO"
ORG_PHONE = "WEKA SIMU"
ORG_EMAIL = "WEKA EMAIL"
ORG_ADDRESS = "WEKA ANWANI"

BRANCH_CODE = "HQ"
BRANCH_NAME = "MAIN BRANCH"
BRANCH_LOCATION = "WEKA LOCATION HALISI"

with app.app_context():
    with ext.engine.connect() as conn:
        existing_org = conn.execute(
            text("SELECT id FROM organizations WHERE name = :name LIMIT 1"),
            {"name": ORG_NAME}
        ).fetchone()

        if existing_org:
            organization_id = existing_org[0]
        else:
            organization_id = conn.execute(
                text("""
                    INSERT INTO organizations (name, short_name, tin, phone, email, address, is_active)
                    VALUES (:name, :short_name, :tin, :phone, :email, :address, TRUE)
                    RETURNING id
                """),
                {
                    "name": ORG_NAME,
                    "short_name": ORG_SHORT_NAME,
                    "tin": ORG_TIN,
                    "phone": ORG_PHONE,
                    "email": ORG_EMAIL,
                    "address": ORG_ADDRESS,
                }
            ).scalar_one()

        conn.execute(
            text("""
                INSERT INTO branches (organization_id, code, name, location, is_active)
                VALUES (:organization_id, :code, :name, :location, TRUE)
                ON CONFLICT (code) DO UPDATE SET
                    organization_id = EXCLUDED.organization_id,
                    name = EXCLUDED.name,
                    location = EXCLUDED.location,
                    is_active = EXCLUDED.is_active
            """),
            {
                "organization_id": organization_id,
                "code": BRANCH_CODE,
                "name": BRANCH_NAME,
                "location": BRANCH_LOCATION,
            }
        )

        conn.commit()

print("Organization and branch saved successfully.")