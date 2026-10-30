"""
Dataset Management Service for ExamForge AI
Handles CSV upload, encoding detection, column mapping, validation, and question bank ingestion.
Strictly enforces Tamil Nadu State Board (Classes 6–12) requirements.
"""

import os
import sys
import re
import json
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config
from database.db import SessionLocal
from database.models import DatasetUpload, Question, AuditLog
from services.curriculum_service import TN_CLASSES, get_supported_classes

UPLOADS_DIR = os.path.join(Config.DATA_DIR, 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

STANDARD_FIELDS = [
    'question',
    'class_grade',
    'subject',
    'topic',
    'board',
    'question_type',
    'marks',
    'bloom_level',
    'difficulty'
]

VALID_BLOOM_LEVELS = {'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'}
VALID_DIFFICULTY_LEVELS = {'easy', 'medium', 'hard'}

BLOOM_TITLE_MAP = {
    'remember': 'Remember',
    'understand': 'Understand',
    'apply': 'Apply',
    'analyze': 'Analyze',
    'evaluate': 'Evaluate',
    'create': 'Create'
}

DIFF_TITLE_MAP = {
    'easy': 'Easy',
    'medium': 'Medium',
    'hard': 'Hard'
}


def normalize_class_grade(val):
    """Normalize varied class representations (e.g., '10', 'Class 10', '10th', 'X') to 'Class 10'."""
    if not val or pd.isna(val):
        return None
    s = str(val).strip()
    roman_map = {'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10', 'xi': '11', 'xii': '12'}
    
    # Check roman
    lower_s = s.lower().replace('class', '').replace('grade', '').replace('std', '').replace('th', '').strip()
    if lower_s in roman_map:
        return f"Class {roman_map[lower_s]}"
    
    # Match digits
    m = re.search(r'\b(6|7|8|9|10|11|12)\b', s)
    if m:
        return f"Class {m.group(1)}"
    
    if s in TN_CLASSES:
        return s
    return None


def detect_file_encoding(filepath):
    """Detect text encoding across common formats."""
    for enc in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                f.read(4096)
            return enc
        except (UnicodeDecodeError, Exception):
            continue
    return 'utf-8'


def suggest_column_mappings(columns):
    """Suggest standard field mappings for uploaded CSV column headers."""
    mapping = {}
    for col in columns:
        c_clean = str(col).strip().lower().replace('_', ' ').replace('-', ' ')
        if any(k in c_clean for k in ['question text', 'question', 'problem', 'item', 'query']):
            if 'question' not in mapping.values():
                mapping[col] = 'question'
        elif any(k in c_clean for k in ['class grade', 'class', 'grade', 'standard', 'std']):
            if 'class_grade' not in mapping.values():
                mapping[col] = 'class_grade'
        elif any(k in c_clean for k in ['subject name', 'subject', 'course', 'discipline']):
            if 'subject' not in mapping.values():
                mapping[col] = 'subject'
        elif any(k in c_clean for k in ['chapter', 'topic', 'unit', 'lesson']):
            if 'topic' not in mapping.values():
                mapping[col] = 'topic'
        elif any(k in c_clean for k in ['board', 'curriculum', 'education board']):
            if 'board' not in mapping.values():
                mapping[col] = 'board'
        elif any(k in c_clean for k in ['question type', 'type', 'format']):
            if 'question_type' not in mapping.values():
                mapping[col] = 'question_type'
        elif any(k in c_clean for k in ['marks', 'max marks', 'score', 'points', 'weightage']):
            if 'marks' not in mapping.values():
                mapping[col] = 'marks'
        elif any(k in c_clean for k in ['bloom level', 'bloom', 'cognitive', 'taxonomy']):
            if 'bloom_level' not in mapping.values():
                mapping[col] = 'bloom_level'
        elif any(k in c_clean for k in ['difficulty level', 'difficulty', 'diff']):
            if 'difficulty' not in mapping.values():
                mapping[col] = 'difficulty'
    return mapping


def save_uploaded_csv(file_storage, user_id=None):
    """
    Saves uploaded CSV file, detects encoding, reads sample preview,
    and creates a DatasetUpload tracking record.
    """
    filename = file_storage.filename
    if not filename.lower().endswith('.csv'):
        return {'success': False, 'error': 'Uploaded file must be a CSV (.csv) file.'}

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = "".join(c for c in filename if c.isalnum() or c in '._-')
    saved_filename = f"{timestamp}_{safe_name}"
    filepath = os.path.join(UPLOADS_DIR, saved_filename)

    file_storage.save(filepath)

    encoding = detect_file_encoding(filepath)
    try:
        df = pd.read_csv(filepath, encoding=encoding)
    except Exception as e:
        return {'success': False, 'error': f'Failed to parse CSV file: {str(e)}'}

    columns = list(df.columns)
    suggested_map = suggest_column_mappings(columns)
    preview_rows = df.head(10).fillna('').to_dict(orient='records')
    total_rows = len(df)

    db = SessionLocal()
    try:
        record = DatasetUpload(
            filename=saved_filename,
            original_filename=filename,
            board='Tamil Nadu State Board',
            uploaded_by=user_id,
            total_rows=total_rows,
            status='uploaded',
            validation_report={
                'encoding': encoding,
                'columns': columns,
                'suggested_mapping': suggested_map,
                'total_rows': total_rows
            }
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return {
            'success': True,
            'dataset_id': record.id,
            'filename': saved_filename,
            'original_filename': filename,
            'total_rows': total_rows,
            'encoding': encoding,
            'columns': columns,
            'suggested_mapping': suggested_map,
            'preview_sample': preview_rows,
            'standard_fields': STANDARD_FIELDS
        }
    finally:
        db.close()


def validate_dataset(upload_id: int, column_mapping: dict, default_class: str = None, default_board: str = 'Tamil Nadu State Board', user_id: int = None):
    """
    Validates CSV contents according to specified column mapping.
    Verifies Tamil Nadu State Board restriction, Class 6-12 adherence,
    deduplication, and label coverage.
    """
    db = SessionLocal()
    try:
        upload = db.get(DatasetUpload, upload_id)
        if not upload:
            return {'success': False, 'error': 'Dataset upload record not found.'}

        filepath = os.path.join(UPLOADS_DIR, upload.filename)
        if not os.path.exists(filepath):
            return {'success': False, 'error': 'Underlying CSV file not found on disk.'}

        encoding = detect_file_encoding(filepath)
        df = pd.read_csv(filepath, encoding=encoding)

        # Invert column_mapping: standard_field -> csv_column
        std_to_csv = {v: k for k, v in column_mapping.items() if v in STANDARD_FIELDS}

        if 'question' not in std_to_csv:
            return {'success': False, 'error': 'Column mapping must map at least the "question" field.'}

        valid_rows = []
        invalid_rows = []
        seen_questions = set()
        duplicate_count = 0

        # Existing DB question texts for collision detection
        existing_db_texts = set(
            q[0].strip().lower() for q in db.query(Question.question).all() if q[0]
        )

        class_dist = {}
        subject_dist = {}
        bloom_dist = {}
        diff_dist = {}

        for idx, row in df.iterrows():
            row_num = idx + 2  # 1-indexed header + 1
            q_col = std_to_csv.get('question')
            raw_q = str(row.get(q_col, '')).strip()

            if not raw_q or raw_q.lower() == 'nan':
                invalid_rows.append({'row': row_num, 'reason': 'Missing or empty question text'})
                continue

            q_clean_lower = raw_q.lower()
            if q_clean_lower in seen_questions:
                duplicate_count += 1
                continue
            seen_questions.add(q_clean_lower)

            # Class validation
            c_col = std_to_csv.get('class_grade')
            raw_class = row.get(c_col) if c_col else default_class
            norm_class = normalize_class_grade(raw_class)
            if not norm_class or norm_class not in TN_CLASSES:
                invalid_rows.append({
                    'row': row_num,
                    'reason': f"Invalid class '{raw_class}'. Must be one of Classes 6 to 12 for Tamil Nadu State Board."
                })
                continue

            # Board validation: Tamil Nadu State Board only!
            b_col = std_to_csv.get('board')
            raw_board = str(row.get(b_col, '')).strip() if b_col else default_board
            if raw_board and raw_board.lower() not in [
                'tamil nadu state board', 'tamil nadu', 'samacheer kalvi', 'tn state board', 'state board'
            ]:
                invalid_rows.append({
                    'row': row_num,
                    'reason': f"Unsupported board '{raw_board}'. Application strictly supports Tamil Nadu State Board."
                })
                continue

            # Subject validation
            s_col = std_to_csv.get('subject')
            raw_subject = str(row.get(s_col, '')).strip() if s_col else 'General'
            if not raw_subject or raw_subject.lower() == 'nan':
                raw_subject = 'General'

            # Topic / Chapter
            t_col = std_to_csv.get('topic')
            raw_topic = str(row.get(t_col, '')).strip() if t_col and pd.notna(row.get(t_col)) else None

            # Marks
            m_col = std_to_csv.get('marks')
            marks_val = None
            if m_col and pd.notna(row.get(m_col)):
                try:
                    marks_val = float(row.get(m_col))
                except (ValueError, TypeError):
                    marks_val = None

            # Bloom Level
            bl_col = std_to_csv.get('bloom_level')
            bloom_val = None
            if bl_col and pd.notna(row.get(bl_col)):
                b_str = str(row.get(bl_col)).strip().lower()
                if b_str in VALID_BLOOM_LEVELS:
                    bloom_val = BLOOM_TITLE_MAP[b_str]
                    bloom_dist[bloom_val] = bloom_dist.get(bloom_val, 0) + 1

            # Difficulty
            d_col = std_to_csv.get('difficulty')
            diff_val = None
            if d_col and pd.notna(row.get(d_col)):
                d_str = str(row.get(d_col)).strip().lower()
                if d_str in VALID_DIFFICULTY_LEVELS:
                    diff_val = DIFF_TITLE_MAP[d_str]
                    diff_dist[diff_val] = diff_dist.get(diff_val, 0) + 1

            # Type
            type_col = std_to_csv.get('question_type')
            q_type = str(row.get(type_col)).strip() if type_col and pd.notna(row.get(type_col)) else 'Short Answer'

            # Update distribution counters
            class_dist[norm_class] = class_dist.get(norm_class, 0) + 1
            subject_dist[raw_subject] = subject_dist.get(raw_subject, 0) + 1

            valid_rows.append({
                'question': raw_q,
                'class_grade': norm_class,
                'subject': raw_subject,
                'topic': raw_topic,
                'board': 'Tamil Nadu State Board',
                'question_type': q_type,
                'marks': marks_val,
                'bloom_level': bloom_val,
                'difficulty': diff_val,
                'is_existing_in_db': q_clean_lower in existing_db_texts
            })

        # Save validation results
        validation_report = {
            'total_rows': len(df),
            'valid_rows_count': len(valid_rows),
            'invalid_rows_count': len(invalid_rows),
            'duplicate_in_file_count': duplicate_count,
            'existing_in_db_count': sum(1 for r in valid_rows if r['is_existing_in_db']),
            'new_unique_questions': sum(1 for r in valid_rows if not r['is_existing_in_db']),
            'class_distribution': class_dist,
            'subject_distribution': subject_dist,
            'bloom_distribution': bloom_dist,
            'difficulty_distribution': diff_dist,
            'bloom_trainable': sum(bloom_dist.values()) >= 20,
            'difficulty_trainable': sum(diff_dist.values()) >= 20,
            'errors_sample': invalid_rows[:15],
            'column_mapping': column_mapping,
            'validated_at': datetime.now(timezone.utc).isoformat()
        }

        upload.total_rows = len(df)
        upload.valid_rows = len(valid_rows)
        upload.invalid_rows = len(invalid_rows)
        upload.duplicate_rows = duplicate_count
        upload.classes_covered = sorted(list(class_dist.keys()))
        upload.subjects_covered = sorted(list(subject_dist.keys()))
        upload.validation_report = validation_report
        upload.status = 'ready_for_training' if len(valid_rows) > 0 else 'rejected'
        db.commit()

        # Audit log
        entry = AuditLog(
            user_id=user_id,
            action="VALIDATE_DATASET",
            entity_type="DatasetUpload",
            entity_id=str(upload.id),
            details={'valid': len(valid_rows), 'invalid': len(invalid_rows)}
        )
        db.add(entry)
        db.commit()

        return {
            'success': True,
            'dataset_id': upload.id,
            'status': upload.status,
            'report': validation_report,
            'sample_valid': valid_rows[:5]
        }

    except Exception as e:
        db.rollback()
        return {'success': False, 'error': f'Validation failed: {str(e)}'}
    finally:
        db.close()


def commit_dataset_to_question_bank(upload_id: int, user_id: int = None):
    """
    Inserts validated Tamil Nadu State Board questions from upload into the live question bank.
    """
    db = SessionLocal()
    try:
        upload = db.get(DatasetUpload, upload_id)
        if not upload:
            return {'success': False, 'error': 'Dataset upload record not found.'}

        rep = upload.validation_report
        if not rep or upload.status not in ['ready_for_training', 'validated']:
            return {'success': False, 'error': 'Dataset must be validated before committing to question bank.'}

        filepath = os.path.join(UPLOADS_DIR, upload.filename)
        encoding = detect_file_encoding(filepath)
        df = pd.read_csv(filepath, encoding=encoding)
        col_map = rep.get('column_mapping', {})

        std_to_csv = {v: k for k, v in col_map.items() if v in STANDARD_FIELDS}

        inserted = 0
        skipped = 0
        existing_texts = set(
            q[0].strip().lower() for q in db.query(Question.question).all() if q[0]
        )

        for idx, row in df.iterrows():
            q_col = std_to_csv.get('question')
            raw_q = str(row.get(q_col, '')).strip() if q_col else ''
            if not raw_q or raw_q.lower() in existing_texts:
                skipped += 1
                continue

            c_col = std_to_csv.get('class_grade')
            cls = normalize_class_grade(row.get(c_col)) if c_col else 'Class 10'
            if not cls or cls not in TN_CLASSES:
                skipped += 1
                continue

            s_col = std_to_csv.get('subject')
            subj = str(row.get(s_col)).strip() if s_col and pd.notna(row.get(s_col)) else 'General'

            t_col = std_to_csv.get('topic')
            top = str(row.get(t_col)).strip() if t_col and pd.notna(row.get(t_col)) else None

            m_col = std_to_csv.get('marks')
            marks = None
            if m_col and pd.notna(row.get(m_col)):
                try:
                    marks = float(row.get(m_col))
                except Exception:
                    marks = None

            bl_col = std_to_csv.get('bloom_level')
            bloom = None
            if bl_col and pd.notna(row.get(bl_col)):
                b_str = str(row.get(bl_col)).strip().lower()
                bloom = BLOOM_TITLE_MAP.get(b_str)

            d_col = std_to_csv.get('difficulty')
            diff = None
            if d_col and pd.notna(row.get(d_col)):
                d_str = str(row.get(d_col)).strip().lower()
                diff = DIFF_TITLE_MAP.get(d_str)

            type_col = std_to_csv.get('question_type')
            q_type = str(row.get(type_col)).strip() if type_col and pd.notna(row.get(type_col)) else 'Short Answer'

            qid = f"TNSB_UP_{upload.id}_{idx + 1}"
            q = Question(
                question_id=qid,
                question=raw_q,
                subject=subj,
                topic=top,
                board='Tamil Nadu State Board',
                class_grade=cls,
                question_type=q_type,
                marks=marks,
                bloom_level=bloom,
                difficulty=diff,
                source=f"Admin Upload: {upload.original_filename}",
                dataset_upload_id=upload.id,
                verified=True
            )
            db.add(q)
            existing_texts.add(raw_q.lower())
            inserted += 1

            if inserted % 250 == 0:
                db.commit()

        db.commit()

        upload.status = 'trained'
        db.commit()

        # Audit log
        entry = AuditLog(
            user_id=user_id,
            action="COMMIT_DATASET_TO_BANK",
            entity_type="DatasetUpload",
            entity_id=str(upload.id),
            details={'inserted': inserted, 'skipped': skipped}
        )
        db.add(entry)
        db.commit()

        return {
            'success': True,
            'inserted_count': inserted,
            'skipped_count': skipped,
            'message': f"Successfully committed {inserted} Tamil Nadu State Board questions to the Question Bank."
        }

    except Exception as e:
        db.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        db.close()
