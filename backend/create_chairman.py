"""
ExamForge AI — CLI Tool: Create Initial Chairman Account
Interactive prompt without hardcoded credentials.
"""

import os
import sys
import getpass
import re

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from database.db import SessionLocal, init_db
from database.models import User, AuditLog
from services.auth import hash_password, log_audit


def prompt_chairman_creation():
    print("=" * 65)
    print(" ExamForge AI — Institutional Chairman Account Provisioning CLI")
    print("=" * 65)
    print("Note: The Chairman is the highest-level institutional account.")
    print("      No default or hardcoded credentials are used.\n")

    init_db()
    db = SessionLocal()

    try:
        # Prompt for email
        while True:
            email = input("Enter Chairman Email Address: ").strip().lower()
            if not email:
                print("Email address cannot be empty. Please try again.")
                continue
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                print("Invalid email format. Please enter a valid email address.")
                continue
            break

        # Prompt for Full Name
        full_name = input("Enter Full Name (e.g., Dr. S. K. Chairman): ").strip()
        if not full_name:
            full_name = "Institutional Chairman"

        # Prompt for Phone (optional)
        phone = input("Enter Contact Phone (optional): ").strip()

        # Prompt for Password (hidden)
        while True:
            password = getpass.getpass("Enter Secure Password (min 6 characters): ")
            if len(password) < 6:
                print("Password must be at least 6 characters long. Please try again.")
                continue
            password_confirm = getpass.getpass("Confirm Password: ")
            if password != password_confirm:
                print("Passwords do not match. Please try again.")
                continue
            break

        # Check existing user
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            print(f"\nUser with email '{email}' already exists with role '{existing.role}'.")
            confirm = input("Do you want to update this user to Chairman and reset password? (y/N): ").strip().lower()
            if confirm != 'y':
                print("Aborting Chairman account provisioning.")
                return False

            existing.role = 'chairman'
            existing.full_name = full_name
            if phone:
                existing.phone = phone
            existing.password_hash = hash_password(password)
            existing.is_active = True
            db.commit()
            log_audit(db, action="UPDATE_CHAIRMAN_ACCOUNT", entity_type="User", entity_id=existing.id, user=existing)
            print(f"\n[SUCCESS] Successfully updated '{email}' to Chairman role.")
            return True
        else:
            new_chairman = User(
                email=email,
                full_name=full_name,
                phone=phone,
                role='chairman',
                password_hash=hash_password(password),
                is_active=True
            )
            db.add(new_chairman)
            db.commit()
            db.refresh(new_chairman)
            log_audit(db, action="CREATE_CHAIRMAN_ACCOUNT", entity_type="User", entity_id=new_chairman.id, user=new_chairman)
            print(f"\n[SUCCESS] Chairman account created successfully for '{email}' (ID: {new_chairman.id}).")
            return True

    finally:
        db.close()


if __name__ == '__main__':
    prompt_chairman_creation()

