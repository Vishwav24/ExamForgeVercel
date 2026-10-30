"""
Database connection setup and safe migration utilities using SQLAlchemy.
"""

import os
import sys
import sqlite3
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config

# Ensure database directory exists
os.makedirs(os.path.join(Config.BASE_DIR, 'database'), exist_ok=True)

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, echo=False)
SessionLocal = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def safe_migrate_existing_tables():
    """
    Safely adds missing columns to existing SQLite tables without dropping data.
    """
    db_path = os.path.join(Config.BASE_DIR, 'database', 'examforge.db')
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Column additions to check
    column_checks = [
        ('users', 'phone', 'TEXT'),
        ('users', 'subject_specialization', 'TEXT'),
        ('users', 'updated_at', 'DATETIME'),
        ('questions', 'dataset_upload_id', 'INTEGER'),
        ('questions', 'updated_at', 'DATETIME'),
        ('generated_papers', 'duration_minutes', 'INTEGER DEFAULT 90'),
        ('generated_papers', 'created_by_user_id', 'INTEGER'),
        ('generated_papers', 'sections_json', 'JSON'),
    ]

    for table, col_name, col_type in column_checks:
        try:
            cursor.execute(f"PRAGMA table_info({table});")
            existing_cols = [c[1] for c in cursor.fetchall()]
            if existing_cols and col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};")
                conn.commit()
                print(f"Migrated {table}: added column {col_name}")
        except Exception as e:
            print(f"Migration notice for {table}.{col_name}: {e}")

    conn.close()


def init_db():
    """Initialize database tables, safe migrations, and initial schema."""
    from database.models import User, Curriculum, DatasetUpload, ModelVersion, AuditLog, Question, GeneratedPaper
    Base.metadata.create_all(bind=engine)
    safe_migrate_existing_tables()
    print("Database tables initialized and verified.")
