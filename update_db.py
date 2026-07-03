import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'project_management.db')

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE document ADD COLUMN task_id INTEGER")
        print("Successfully added task_id to document table.")
    except sqlite3.OperationalError as e:
        print(f"OperationalError (possibly column already exists): {e}")
    conn.commit()
    conn.close()
    
from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    db.create_all()
    print("Database tables created/updated successfully via SQLAlchemy.")
