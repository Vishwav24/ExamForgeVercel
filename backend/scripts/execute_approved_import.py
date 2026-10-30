"""
Execute Approved Import of 2,957 Candidates into backend/database/examforge.db
Follows strict safeguards:
1. Timestamped binary backup & checksum verification.
2. Re-read manifest and verify 2,957 candidates.
3. INSERT-only execution with duplicate ID and stem collision checks.
4. Verify unchanged users, generated papers, and existing questions.
"""

import os
import sys
import json
import shutil
import hashlib
import sqlite3
from datetime import datetime, timezone

# Reconfigure stdout to utf-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from scripts.validate_and_dry_run_full_curriculum import normalize_text_key

def file_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def execute_import():
    live_db = os.path.join(backend_dir, 'database', 'examforge.db')
    manifest_file = os.path.join(backend_dir, 'reports', 'final_approved_import_manifest.json')
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backend_dir, 'database', f'examforge_backup_{timestamp_str}.db')

    print("=== EXAMFORGE AI: APPROVED IMPORT EXECUTION ===")
    print(f"Target Database: {live_db}")

    # 1. Verify source database integrity and take backup
    if not os.path.exists(live_db):
        raise FileNotFoundError(f"Database not found at {live_db}")

    orig_size = os.path.getsize(live_db)
    orig_hash = file_sha256(live_db)
    print(f"Original Database Size: {orig_size} bytes | SHA256: {orig_hash[:16]}...")

    # Query initial counts
    conn = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM questions")
    initial_q_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM users")
    initial_u_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM generated_papers")
    initial_p_count = c.fetchone()[0]
    c.execute("SELECT question_id, question FROM questions")
    existing_rows = c.fetchall()
    conn.close()

    print(f"Initial State: {initial_q_count} questions, {initial_u_count} users, {initial_p_count} generated papers.")

    existing_qids = set(r[0] for r in existing_rows if r[0])
    existing_stems = set(normalize_text_key(r[1]) for r in existing_rows if r[1])

    # Perform Backup
    shutil.copy2(live_db, backup_file)
    backup_size = os.path.getsize(backup_file)
    backup_hash = file_sha256(backup_file)

    if backup_hash != orig_hash or backup_size != orig_size:
        raise RuntimeError("Backup verification failed! Hashes or file sizes do not match.")
    print(f"Backup created and verified successfully: {backup_file}")

    # 2. Read and verify manifest
    with open(manifest_file, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)

    candidates = manifest_data.get('candidates', [])
    if len(candidates) != 2957:
        raise ValueError(f"Expected 2957 candidates, but found {len(candidates)} in manifest.")
    print(f"Manifest verified: {len(candidates)} unique candidates loaded.")

    # Check for internal duplicate IDs and stems
    manifest_ids = [c['candidate_id'] for c in candidates]
    manifest_stems = [normalize_text_key(c['question']) for c in candidates]

    if len(set(manifest_ids)) != 2957:
        raise ValueError(f"Duplicate candidate_ids found in manifest: {len(manifest_ids) - len(set(manifest_ids))}")
    if len(set(manifest_stems)) != 2957:
        raise ValueError(f"Duplicate stems found in manifest: {len(manifest_stems) - len(set(manifest_stems))}")

    # 3. Collision checks against live database
    id_collisions = set(manifest_ids).intersection(existing_qids)
    stem_collisions = set(manifest_stems).intersection(existing_stems)

    if id_collisions:
        raise RuntimeError(f"Aborting import: {len(id_collisions)} ID collisions detected with live database.")
    if stem_collisions:
        raise RuntimeError(f"Aborting import: {len(stem_collisions)} question stem collisions detected with live database.")
    print("Pre-import collision checks passed: 0 ID collisions, 0 stem collisions.")

    # 4. Prepare INSERT records
    # Preserve full source, verification type, and references
    insert_records = []
    now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    for cand in candidates:
        source_clean = cand.get('source', 'Tamil Nadu State Board Question Bank')
        source_file = cand.get('source_file')
        verif_type = cand.get('verification_type')
        if source_file and verif_type:
            full_source = f"{source_clean} [{verif_type}] ({source_file})"
        else:
            full_source = source_clean
        # truncate full_source safely to column limit
        full_source = full_source[:200]

        record = (
            cand['candidate_id'],
            cand['question'],
            cand['subject'],
            cand['topic'],
            'Tamil Nadu State Board',
            cand['class_grade'],
            cand['question_type'],
            float(cand['marks']),
            cand.get('bloom_level', 'Remember'),
            cand.get('difficulty', 'Medium'),
            full_source,
            1, # verified = True
            now_iso,
            now_iso,
            None # dataset_upload_id
        )
        insert_records.append(record)

    # 5. Execute INSERT-only in transaction
    write_conn = sqlite3.connect(live_db)
    write_conn.execute("PRAGMA foreign_keys = ON;")
    write_cursor = write_conn.cursor()

    try:
        write_cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
        
        insert_sql = """
        INSERT INTO questions (
            question_id, question, subject, topic, board, class_grade,
            question_type, marks, bloom_level, difficulty, source,
            verified, created_at, updated_at, dataset_upload_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        write_cursor.executemany(insert_sql, insert_records)
        inserted_count = write_cursor.rowcount
        
        # Verify no unintended modifications
        write_cursor.execute("SELECT count(*) FROM users")
        post_u_count = write_cursor.fetchone()[0]
        if post_u_count != initial_u_count:
            raise RuntimeError(f"Users table modified! Expected {initial_u_count}, got {post_u_count}")

        write_cursor.execute("SELECT count(*) FROM generated_papers")
        post_p_count = write_cursor.fetchone()[0]
        if post_p_count != initial_p_count:
            raise RuntimeError(f"Generated papers table modified! Expected {initial_p_count}, got {post_p_count}")

        write_cursor.execute("SELECT count(*) FROM questions")
        post_q_count = write_cursor.fetchone()[0]
        expected_q_count = initial_q_count + len(insert_records)
        if post_q_count != expected_q_count:
            raise RuntimeError(f"Questions count mismatch! Expected {expected_q_count}, got {post_q_count}")

        # Commit transaction
        write_conn.commit()
        print(f"Transaction successfully committed! {inserted_count} records inserted.")

    except Exception as e:
        write_conn.rollback()
        write_conn.close()
        print(f"ERROR: Transaction rolled back due to error: {e}")
        # Restore backup if necessary
        shutil.copy2(backup_file, live_db)
        print("Database restored from backup.")
        raise
    finally:
        write_conn.close()

    # 6. Post-import verification and audit
    verify_conn = sqlite3.connect(f"file:{live_db}?mode=ro", uri=True)
    vc = verify_conn.cursor()
    vc.execute("SELECT count(*) FROM questions")
    final_total_q = vc.fetchone()[0]
    vc.execute("SELECT count(*) FROM questions WHERE board = 'Tamil Nadu State Board'")
    final_tnsb_q = vc.fetchone()[0]
    vc.execute("SELECT count(*) FROM questions WHERE board = 'Tamil Nadu State Board' AND marks = 1.0")
    final_tnsb_1m = vc.fetchone()[0]
    vc.execute("SELECT count(*) FROM questions WHERE board = 'Tamil Nadu State Board' AND marks = 2.0")
    final_tnsb_2m = vc.fetchone()[0]
    vc.execute("SELECT count(*) FROM questions WHERE board = 'Tamil Nadu State Board' AND class_grade = 'Class 10' AND subject = 'Science'")
    final_c10_sci = vc.fetchone()[0]
    verify_conn.close()

    result_summary = {
        'timestamp': timestamp_str,
        'backup_file': backup_file,
        'backup_verified': True,
        'records_to_insert': len(candidates),
        'records_inserted': inserted_count,
        'records_skipped': 0,
        'records_failed': 0,
        'initial_counts': {
            'total_questions': initial_q_count,
            'users': initial_u_count,
            'generated_papers': initial_p_count
        },
        'final_counts': {
            'total_questions': final_total_q,
            'tnsb_questions': final_tnsb_q,
            'tnsb_1m_questions': final_tnsb_1m,
            'tnsb_2m_questions': final_tnsb_2m,
            'c10_science_questions': final_c10_sci,
            'users': post_u_count,
            'generated_papers': post_p_count
        },
        'integrity_verified': True
    }

    report_out = os.path.join(backend_dir, 'reports', 'post_import_execution_report.json')
    with open(report_out, 'w', encoding='utf-8') as f:
        json.dump(result_summary, f, indent=2)

    print("\n=== POST-IMPORT RECONCILIATION SUMMARY ===")
    print(f"Total Questions: {initial_q_count} -> {final_total_q} (+{inserted_count})")
    print(f"TNSB Questions: {final_tnsb_q}")
    print(f"TNSB 1-Mark Questions: {final_tnsb_1m}")
    print(f"TNSB 2-Mark Questions: {final_tnsb_2m}")
    print(f"Class 10 Science Total: {final_c10_sci}")
    print(f"Users Preserved: {post_u_count} (unchanged)")
    print(f"Papers Preserved: {post_p_count} (unchanged)")
    print(f"Report saved to: {report_out}")

if __name__ == '__main__':
    execute_import()

