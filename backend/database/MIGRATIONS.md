# ExamForge AI — Database Migration & Safety Procedure

## Overview
ExamForge AI operates on a **strict non-destructive database policy**. Under no circumstances should existing question banks, user accounts, audit trails, or curriculum metadata be dropped, wiped, or truncated.

All schema evolutions follow additive migration practices.

---

## 1. Automated Safe Migrations (`backend/database/db.py`)
When the Flask server starts (`python app.py`), `init_db()` executes:
1. `Base.metadata.create_all(bind=engine)`:
   - Creates any new tables defined in `backend/database/models.py` (e.g., `curriculum`, `dataset_uploads`, `model_versions`, `audit_logs`).
   - Leaves all existing tables (`users`, `questions`, `generated_papers`) and their rows completely untouched.
2. `safe_migrate_existing_tables()`:
   - Queries `PRAGMA table_info(<table>)` using SQLite connection.
   - Inspects existing table column names.
   - Non-destructively executes `ALTER TABLE <table> ADD COLUMN <name> <type>` only if the column does not already exist.

---

## 2. Manual Schema Evolution Workflow

When adding new tables or columns:
1. **Always take a timestamped backup first**:
   ```powershell
   $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
   Copy-Item "backend\database\examforge.db" -Destination "backend\backups\backup_$timestamp\examforge.db"
   ```
2. **Add model definition** in `backend/database/models.py` with `__table_args__ = {'extend_existing': True}`.
3. **Register new column checks** in `safe_migrate_existing_tables()` within `backend/database/db.py`.
4. **Run unit tests** before restarting production:
   ```powershell
   python -m unittest backend/tests/test_full_system_verification.py
   ```

---

## 3. Disaster Recovery & Rollback Procedure

If any unexpected database condition occurs:
1. Stop the running Flask backend:
   ```powershell
   # Press Ctrl+C in the backend terminal
   ```
2. Restore from the latest verified timestamped backup:
   ```powershell
   Copy-Item "backend\backups\backup_20261014_stage0\database\examforge.db" -Destination "backend\database\examforge.db" -Force
   ```
3. Restart the backend:
   ```powershell
   python app.py
   ```
4. Verify table integrity and row counts via `test_full_system_verification.py`.
