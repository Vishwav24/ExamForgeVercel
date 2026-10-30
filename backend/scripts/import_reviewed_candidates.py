"""
Import Reviewed Candidate Questions into Question Bank (Transactional & Safe)
Supports:
1. Dry-run reporting by default (zero database modifications).
2. Automated SQLite database backup before commit.
3. Clean chapter name normalization matching TNSB curriculum.
4. Duplicate text collision avoidance.
5. Ground-truth provenance metadata tracking.
"""

import os
import sys
import shutil
import json
import argparse
from datetime import datetime
import pandas as pd

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from database.db import SessionLocal, engine
from database.models import Question, AuditLog
from services.curriculum_service import get_supported_chapters

def normalize_math_chapter(raw_ch):
    s = str(raw_ch).strip()
    sl = s.lower()
    if 'relation' in sl or 'பயிற்சி -1' in s or 'பயிற்சி-1' in s:
        return 'Relations and Functions'
    if 'number' in sl or 'முழுஎண்கள்' in s or 'பயிற்சி-2' in s or 'பயிற்சி -2' in s:
        return 'Numbers and Sequences'
    if 'algebra' in sl or 'பயிற்சி-3' in s or 'பயிற்சி -3' in s:
        return 'Algebra'
    if 'coordinate' in sl or 'unit 5' in sl or 'பயிற்சி- 5' in s or 'பயிற்சி-5' in s:
        return 'Coordinate Geometry'
    if 'trigonometry' in sl or 'unit 6' in sl or 'பயிற்சி: 6' in s:
        return 'Trigonometry'
    if 'mensuration' in sl or 'unit 7' in sl or 'பயிற்சி 7' in s:
        return 'Mensuration'
    if 'statistic' in sl or 'probability' in sl or 'unit 8' in sl:
        return 'Statistics and Probability'
    if 'geometry' in sl or 'unit 4' in sl or 'பயிற்சி: 4' in s:
        return 'Geometry'
    return s


def dry_run_report(csv_path, subject='Mathematics', class_grade='Class 10'):
    if not os.path.exists(csv_path):
        return {'success': False, 'error': f"CSV not found: {csv_path}"}

    df = pd.read_csv(csv_path)
    sub_df = df[(df['subject'] == subject) & (df['suggested_marks'] == 1.0) & (df['validation_status'] == 'candidate_review')]
    
    db = SessionLocal()
    existing_texts = set(q.question.strip().lower() for q in db.query(Question.question).all() if q.question)
    db.close()

    valid_inserts = []
    skipped_duplicates = 0
    chapter_dist = {}

    for _, row in sub_df.iterrows():
        q_text = str(row.get('question_text', '')).strip()
        if not q_text or q_text.lower() in existing_texts:
            skipped_duplicates += 1
            continue

        raw_ch = row.get('chapter_heading')
        norm_ch = normalize_math_chapter(raw_ch) if subject == 'Mathematics' else str(raw_ch).strip()
        chapter_dist[norm_ch] = chapter_dist.get(norm_ch, 0) + 1

        valid_inserts.append({
            'candidate_id': row.get('candidate_id'),
            'class_grade': class_grade,
            'subject': subject,
            'topic': norm_ch,
            'marks': 1.0,
            'question_type': 'Objective',
            'question': q_text,
            'source': f"TNSB Textbook Extracted ({row.get('edition', '2024')})",
            'verified': True
        })

    return {
        'total_candidates_evaluated': len(sub_df),
        'valid_inserts_count': len(valid_inserts),
        'skipped_duplicates_count': skipped_duplicates,
        'chapter_distribution': chapter_dist,
        'sample_inserts': valid_inserts[:3]
    }


def execute_import(csv_path, subject='Mathematics', class_grade='Class 10'):
    rep = dry_run_report(csv_path, subject=subject, class_grade=class_grade)
    if not rep.get('valid_inserts_count'):
        print("No valid inserts found.")
        return False

    # 1. Take a safe backup of SQLite database
    db_path = os.path.join(backend_dir, 'database', 'examforge.db')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"Created pre-import backup at: {backup_path}")

    # 2. Transactional insertion
    db = SessionLocal()
    try:
        inserted_count = 0
        df = pd.read_csv(csv_path)
        sub_df = df[(df['subject'] == subject) & (df['suggested_marks'] == 1.0) & (df['validation_status'] == 'candidate_review')]
        existing_texts = set(q.question.strip().lower() for q in db.query(Question.question).all() if q.question)

        for _, row in sub_df.iterrows():
            q_text = str(row.get('question_text', '')).strip()
            if not q_text or q_text.lower() in existing_texts:
                continue

            raw_ch = row.get('chapter_heading')
            norm_ch = normalize_math_chapter(raw_ch) if subject == 'Mathematics' else str(raw_ch).strip()

            new_q = Question(
                question_id=row.get('candidate_id'),
                question=q_text,
                subject=subject,
                topic=norm_ch,
                board='Tamil Nadu State Board',
                class_grade=class_grade,
                question_type='Objective',
                marks=1.0,
                bloom_level=row.get('bloom_level') or 'Remember',
                difficulty='Easy',
                source=f"TNSB Textbook Extracted ({row.get('edition', '2024')})",
                verified=True
            )
            db.add(new_q)
            existing_texts.add(q_text.lower())
            inserted_count += 1

        db.commit()
        print(f"Successfully committed {inserted_count} reviewed 1-mark questions to {db_path}!")
        return True

    except Exception as e:
        db.rollback()
        print(f"Import failed with error: {e}. Restoring from backup...")
        shutil.copy2(backup_path, db_path)
        print("Database restored to pre-import state.")
        return False
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Import reviewed candidate questions into live question bank.")
    parser.add_argument('--commit', action='store_true', help="Execute import into live database with backup.")
    parser.add_argument('--subject', default='Mathematics', help="Subject to import")
    parser.add_argument('--class_grade', default='Class 10', help="Class to import")
    parser.add_argument('--csv', default='backend/data/extracted_candidates_v2/candidates_class_10.csv', help="Path to candidates CSV")
    
    args = parser.parse_args()
    
    if args.commit:
        execute_import(args.csv, subject=args.subject, class_grade=args.class_grade)
    else:
        rep = dry_run_report(args.csv, subject=args.subject, class_grade=args.class_grade)
        print(json.dumps(rep, indent=2, ensure_ascii=False))

