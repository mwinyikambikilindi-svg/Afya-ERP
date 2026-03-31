from app import create_app
from app.extensions import create_all_tables
import app.models.organization

app = create_app()

with app.app_context():
    create_all_tables()
    print("Table created successfully")