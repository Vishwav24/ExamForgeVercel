"""
Comprehensive Validation and Dry-Run Inspection for Classes 6-12 (TNSB)
Strictly Read-Only: Does NOT modify, delete, or write to examforge.db.
"""

import os
import sys
import re
import json
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from services.curriculum_service import get_supported_chapters, get_supported_subjects, TN_CURRICULUM_DATA, TN_CLASSES

TAMIL_UNICODE_RE = re.compile(r'[\u0b80-\u0bff]')
OCR_GARBAGE_RE = re.compile(r'(\?{3,}|\{1,}|_{4,}|\b[a-zA-Z]{1}\b\s+\b[a-zA-Z]{1}\b\s+\b[a-zA-Z]{1}\b)')
ANSWER_CONTAM_RE = re.compile(r'(?i)\b(Ans(?:wer)?\s*:\s*|Solution\s*:\s*|விடை\s*:\s*)')

def detect_language(text):
    if not text:
        return 'Unknown'
    if TAMIL_UNICODE_RE.search(str(text)):
        return 'Tamil'
    return 'English'

def clean_text(text):
    if pd.isna(text):
        return ''
    return str(text).strip()

def normalize_text_key(text):
    cleaned = re.sub(r'\s+', ' ', str(text).lower().strip())
    cleaned = re.sub(r'[^\w\s\u0b80-\u0bff]', '', cleaned)
    return cleaned

def normalize_chapter_for_subject(raw_chapter, subject, class_grade):
    if pd.isna(raw_chapter) or not str(raw_chapter).strip():
        return None
    raw = str(raw_chapter).strip()
    raw_lower = raw.lower()

    supported = get_supported_chapters(class_grade, subject)
    if not supported:
        return raw

    # 1. Exact case-insensitive match
    for ch in supported:
        if ch.lower() == raw_lower:
            return ch

    # 2. Longest substring matching first (to avoid 'Geometry' matching 'Coordinate Geometry')
    for ch in sorted(supported, key=len, reverse=True):
        if ch.lower() in raw_lower:
            return ch

    # 3. Subject-specific aliases
    if subject == 'Mathematics':
        if 'relation' in raw_lower or 'பயிற்சி -1' in raw or 'பயிற்சி-1' in raw or 'unit 1' in raw_lower:
            for ch in supported:
                if 'relation' in ch.lower() or 'number' in ch.lower():
                    return ch
        if 'number' in raw_lower or 'முழுஎண்கள்' in raw or 'பயிற்சி-2' in raw or 'பயிற்சி -2' in raw:
            for ch in supported:
                if 'number' in ch.lower():
                    return ch
        if 'algebra' in raw_lower or 'பயிற்சி-3' in raw or 'பயிற்சி -3' in raw or 'இயற்கணிதம்' in raw:
            for ch in supported:
                if 'algebra' in ch.lower():
                    return ch
        if 'coordinate' in raw_lower or 'unit 5' in raw_lower or 'ஆயத்தொலை' in raw:
            for ch in supported:
                if 'coordinate' in ch.lower():
                    return ch
        if 'trigonometry' in raw_lower or 'முக்கோணவியல்' in raw:
            for ch in supported:
                if 'trigonometry' in ch.lower():
                    return ch
        if 'mensuration' in raw_lower or 'அளவியல்' in raw:
            for ch in supported:
                if 'mensuration' in ch.lower():
                    return ch
        if 'statistic' in raw_lower or 'probability' in raw_lower or 'நிகழ்தகவு' in raw or 'புள்ளியியல்' in raw:
            for ch in supported:
                if 'statistic' in ch.lower() or 'probability' in ch.lower():
                    return ch
        if 'geometry' in raw_lower or 'வடிவியல்' in raw:
            for ch in supported:
                if 'geometry' in ch.lower():
                    return ch

    if subject == 'Science':
        if 'motion' in raw_lower or 'இயக்க' in raw:
            for ch in supported:
                if 'motion' in ch.lower():
                    return ch
        if 'optic' in raw_lower or 'ஒளியியல்' in raw:
            for ch in supported:
                if 'optic' in ch.lower() or 'light' in ch.lower():
                    return ch
        if 'thermal' in raw_lower or 'heat' in raw_lower or 'வெப்ப' in raw:
            for ch in supported:
                if 'thermal' in ch.lower() or 'heat' in ch.lower():
                    return ch
        if 'electric' in raw_lower or 'மின்னியல்' in raw:
            for ch in supported:
                if 'electric' in ch.lower():
                    return ch
        if 'acoustic' in raw_lower or 'sound' in raw_lower or 'ஒலியியல்' in raw:
            for ch in supported:
                if 'acoustic' in ch.lower() or 'sound' in ch.lower():
                    return ch
        if 'nuclear' in raw_lower or 'அணுக்கரு' in raw:
            for ch in supported:
                if 'nuclear' in ch.lower() or 'atom' in ch.lower():
                    return ch
        if 'periodic' in raw_lower or 'தனிம' in raw:
            for ch in supported:
                if 'periodic' in ch.lower():
                    return ch
        if 'solution' in raw_lower or 'கரைசல்' in raw:
            for ch in supported:
                if 'solution' in ch.lower():
                    return ch
        if 'nervous' in raw_lower or 'நரம்பு' in raw:
            for ch in supported:
                if 'nervous' in ch.lower():
                    return ch
        if 'hormone' in raw_lower or 'ஹார்மோன்' in raw:
            for ch in supported:
                if 'hormone' in ch.lower():
                    return ch
        if 'health' in raw_lower or 'disease' in raw_lower or 'நோய்' in raw or 'உடல் நலம்' in raw:
            for ch in supported:
                if 'health' in ch.lower() or 'disease' in ch.lower():
                    return ch

    return None


def run_full_validation_and_dry_run():
    db_path = os.path.join(backend_dir, 'database', 'examforge.db')
    initial_stat = os.stat(db_path)
    initial_size = initial_stat.st_size
    initial_mtime = initial_stat.st_mtime

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()

    # 1. Baseline Live DB Inspection
    c.execute("SELECT count(*) FROM questions")
    initial_q_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM users")
    initial_u_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM generated_papers")
    initial_p_count = c.fetchone()[0]

    c.execute("SELECT class_grade, subject, topic, marks, question FROM questions WHERE board = 'Tamil Nadu State Board'")
    live_tnsb_rows = c.fetchall()
    conn.close()

    live_text_keys = set()
    live_counts = {}  # (class, subject, topic) -> {'total': X, 'marks': {1:..}}
    for cg, sb, tp, mk, q_txt in live_tnsb_rows:
        mk_val = float(mk) if mk is not None else 0.0
        k = (cg, sb, tp)
        if k not in live_counts:
            live_counts[k] = {'total': 0, 'marks': {1.0: 0, 2.0: 0, 3.0: 0, 5.0: 0, 'other': 0}, 'languages': {'English': 0, 'Tamil': 0}}
        live_counts[k]['total'] += 1
        if mk_val in [1.0, 2.0, 3.0, 5.0]:
            live_counts[k]['marks'][mk_val] += 1
        else:
            live_counts[k]['marks']['other'] += 1
        lang = detect_language(q_txt)
        live_counts[k]['languages'][lang] = live_counts[k]['languages'].get(lang, 0) + 1
        live_text_keys.add(normalize_text_key(q_txt))

    # 2. Phase 2: Source-by-Source Inventory
    source_files = [
        os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_6.csv'),
        os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_7.csv'),
        os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_8.csv'),
        os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_9.csv'),
        os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_10.csv'),
        os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_11.csv'),
        os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_12.csv'),
        os.path.join(backend_dir, 'data', 'discovered_c10_science_candidates_review.csv'),
        os.path.join(backend_dir, 'data', 'tamilnadu_state_board_sample.csv'),
    ]

    source_inventory = []
    seen_candidate_hashes = set()

    all_evaluated_candidates = []

    for s_path in source_files:
        if not os.path.exists(s_path):
            continue
        try:
            df = pd.read_csv(s_path, low_memory=False)
        except Exception as e:
            continue

        cols = list(df.columns)
        rec_count = len(df)
        classes_cov = sorted([str(x) for x in df['class_grade'].dropna().unique() if str(x).strip()]) if 'class_grade' in df.columns else []
        subs_cov = sorted([str(x) for x in df['subject'].dropna().unique() if str(x).strip()]) if 'subject' in df.columns else []
        
        marks_dist = {}
        for mk in [1.0, 2.0, 3.0, 5.0]:
            if 'suggested_marks' in df.columns:
                cnt = int((df['suggested_marks'] == mk).sum())
                if cnt > 0:
                    marks_dist[f"{int(mk)}m"] = cnt
            elif 'marks' in df.columns:
                cnt = int((df['marks'] == mk).sum())
                if cnt > 0:
                    marks_dist[f"{int(mk)}m"] = cnt

        source_inventory.append({
            'source_path': os.path.relpath(s_path, backend_dir).replace('\\', '/'),
            'format': 'CSV',
            'record_count': rec_count,
            'columns': cols,
            'classes_covered': classes_cov,
            'subjects_covered': subs_cov,
            'marks_distribution': marks_dist
        })

    # 3. Phase 3: Validate Question Candidates from primary v2 staging
    # Use individual class files to prevent artificial double-counting with candidates_all_standards.csv
    v2_class_files = [
        ('Class 6', os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_6.csv')),
        ('Class 7', os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_7.csv')),
        ('Class 8', os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_8.csv')),
        ('Class 9', os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_9.csv')),
        ('Class 10', os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_10.csv')),
        ('Class 11', os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_11.csv')),
        ('Class 12', os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_12.csv')),
    ]

    total_candidates = 0
    verified_candidates = []
    needs_review_candidates = []
    rejected_candidates = []
    duplicate_records = []

    seen_text_keys = set()

    for expected_cg, f_path in v2_class_files:
        if not os.path.exists(f_path):
            continue
        df = pd.read_csv(f_path, low_memory=False)
        for idx, row in df.iterrows():
            total_candidates += 1
            cand_id = row.get('candidate_id') or f"GEN_{expected_cg}_{idx}"
            raw_q = clean_text(row.get('question_text') or row.get('question'))
            subject = clean_text(row.get('subject'))
            class_grade = clean_text(row.get('class_grade')) or expected_cg
            raw_ch = row.get('chapter_heading') or row.get('topic')
            raw_marks = row.get('suggested_marks') if 'suggested_marks' in row else row.get('marks')
            val_status = str(row.get('validation_status', '')).lower()
            source = clean_text(row.get('source')) or 'TNSB Textbook Extraction'
            edition = clean_text(row.get('edition')) or '2024'

            # Parse marks
            try:
                marks_val = float(raw_marks) if pd.notna(raw_marks) else None
            except Exception:
                marks_val = None

            lang = detect_language(raw_q)
            norm_key = normalize_text_key(raw_q)

            # Check rejection reasons
            reject_reason = None
            if not raw_q or len(raw_q) < 10:
                reject_reason = 'Question text empty or too short (<10 chars)'
            elif OCR_GARBAGE_RE.search(raw_q):
                reject_reason = 'Malformed OCR text / excessive punctuation glitches'
            elif ANSWER_CONTAM_RE.search(raw_q):
                reject_reason = 'Answer contamination in question stem'
            elif class_grade not in TN_CURRICULUM_DATA:
                reject_reason = f"Class '{class_grade}' not in configured classes"
            elif subject not in TN_CURRICULUM_DATA.get(class_grade, {}):
                reject_reason = f"Subject '{subject}' not configured for {class_grade}"
            elif norm_key in seen_text_keys:
                reject_reason = 'Duplicate within staged candidate repository'
                duplicate_records.append({'candidate_id': cand_id, 'class_grade': class_grade, 'subject': subject, 'reason': reject_reason})
            elif norm_key in live_text_keys:
                reject_reason = 'Collision with existing live question in database'
                duplicate_records.append({'candidate_id': cand_id, 'class_grade': class_grade, 'subject': subject, 'reason': reject_reason})

            if reject_reason:
                rejected_candidates.append({
                    'candidate_id': cand_id,
                    'class_grade': class_grade,
                    'subject': subject,
                    'reason': reject_reason,
                    'sample_text': raw_q[:80]
                })
                continue

            seen_text_keys.add(norm_key)

            # Normalize chapter
            norm_ch = normalize_chapter_for_subject(raw_ch, subject, class_grade)
            supported_chs = get_supported_chapters(class_grade, subject)

            # Assign question type
            if marks_val == 1.0:
                q_type = 'Objective'
            elif marks_val == 2.0:
                q_type = 'Short Answer'
            elif marks_val == 3.0:
                q_type = 'Short Answer'
            elif marks_val == 5.0:
                q_type = 'Detailed'
            else:
                q_type = 'Objective' if val_status == 'candidate_review' else 'Descriptive'

            # Verification vs Needs Review
            if norm_ch and norm_ch in supported_chs and marks_val in [1.0, 2.0, 3.0, 5.0] and val_status == 'candidate_review':
                verified_candidates.append({
                    'candidate_id': cand_id,
                    'class_grade': class_grade,
                    'subject': subject,
                    'topic': norm_ch,
                    'marks': marks_val,
                    'question_type': q_type,
                    'language': lang,
                    'question': raw_q,
                    'bloom_level': clean_text(row.get('bloom_level')) or 'Remember',
                    'difficulty': clean_text(row.get('difficulty')) or ('Easy' if marks_val == 1.0 else 'Medium'),
                    'source': f"TNSB Textbook Extracted ({edition})",
                    'verified': True
                })
            else:
                review_reason = []
                if not norm_ch or norm_ch not in supported_chs:
                    review_reason.append('Unmapped or generic chapter heading')
                if marks_val not in [1.0, 2.0, 3.0, 5.0]:
                    review_reason.append('Marks unassigned or non-standard')
                if val_status != 'candidate_review':
                    review_reason.append(f"Staging status: {val_status}")
                needs_review_candidates.append({
                    'candidate_id': cand_id,
                    'class_grade': class_grade,
                    'subject': subject,
                    'raw_chapter': str(raw_ch),
                    'reasons': review_reason,
                    'sample_text': raw_q[:80]
                })

    # 4. Phase 4: Full Coverage Matrix Across All 45 Pairs and 412 Chapters
    coverage_matrix = {}
    verified_by_k = {}
    for vc in verified_candidates:
        k = (vc['class_grade'], vc['subject'], vc['topic'])
        if k not in verified_by_k:
            verified_by_k[k] = {'total': 0, 'marks': {1.0: 0, 2.0: 0, 3.0: 0, 5.0: 0}, 'languages': {'English': 0, 'Tamil': 0}}
        verified_by_k[k]['total'] += 1
        verified_by_k[k]['marks'][vc['marks']] += 1
        verified_by_k[k]['languages'][vc['language']] += 1

    total_chapters_configured = 0
    matrix_rows = []

    for cg in sorted(TN_CURRICULUM_DATA.keys(), key=lambda x: int(x.split()[1])):
        for sb in TN_CURRICULUM_DATA[cg]:
            chapters = get_supported_chapters(cg, sb)
            total_chapters_configured += len(chapters)
            
            sub_live_total = 0
            sub_live_1m = 0
            sub_live_2m = 0
            sub_live_3m = 0
            sub_live_5m = 0
            
            sub_ver_total = 0
            sub_ver_1m = 0
            sub_ver_2m = 0
            sub_ver_3m = 0
            sub_ver_5m = 0

            chapter_breakdowns = []
            for ch in chapters:
                k = (cg, sb, ch)
                l_data = live_counts.get(k, {'total': 0, 'marks': {1.0: 0, 2.0: 0, 3.0: 0, 5.0: 0, 'other': 0}, 'languages': {'English': 0, 'Tamil': 0}})
                v_data = verified_by_k.get(k, {'total': 0, 'marks': {1.0: 0, 2.0: 0, 3.0: 0, 5.0: 0}, 'languages': {'English': 0, 'Tamil': 0}})

                sub_live_total += l_data['total']
                sub_live_1m += l_data['marks'][1.0]
                sub_live_2m += l_data['marks'][2.0]
                sub_live_3m += l_data['marks'][3.0]
                sub_live_5m += l_data['marks'][5.0]

                sub_ver_total += v_data['total']
                sub_ver_1m += v_data['marks'][1.0]
                sub_ver_2m += v_data['marks'][2.0]
                sub_ver_3m += v_data['marks'][3.0]
                sub_ver_5m += v_data['marks'][5.0]

                chapter_breakdowns.append({
                    'chapter': ch,
                    'live_total': l_data['total'],
                    'live_1m': l_data['marks'][1.0],
                    'live_2m': l_data['marks'][2.0],
                    'live_3m': l_data['marks'][3.0],
                    'live_5m': l_data['marks'][5.0],
                    'verified_candidate_total': v_data['total'],
                    'verified_1m': v_data['marks'][1.0],
                    'verified_2m': v_data['marks'][2.0],
                    'verified_3m': v_data['marks'][3.0],
                    'verified_5m': v_data['marks'][5.0],
                    'projected_post_import_total': l_data['total'] + v_data['total'],
                    'projected_post_import_1m': l_data['marks'][1.0] + v_data['marks'][1.0],
                })

            # Check standard paper generation readiness (5x1m, 5x2m, 5x3m, 4x5m)
            has_live_1m_shortage = (sub_live_1m < 5)
            projected_1m = sub_live_1m + sub_ver_1m
            shortage_resolved = (projected_1m >= 5)

            matrix_rows.append({
                'class_grade': cg,
                'subject': sb,
                'chapters_count': len(chapters),
                'live_total': sub_live_total,
                'live_1m': sub_live_1m,
                'live_2m': sub_live_2m,
                'live_3m': sub_live_3m,
                'live_5m': sub_live_5m,
                'verified_new_total': sub_ver_total,
                'verified_new_1m': sub_ver_1m,
                'verified_new_2m': sub_ver_2m,
                'verified_new_3m': sub_ver_3m,
                'verified_new_5m': sub_ver_5m,
                'projected_total': sub_live_total + sub_ver_total,
                'projected_1m': projected_1m,
                'live_shortage_section_a': has_live_1m_shortage,
                'post_import_solves_section_a': shortage_resolved,
                'chapters': chapter_breakdowns
            })

    # 5. Phase 5: Build Proposed Import Manifest and Dry-Run Summary
    manifest = {
        'generated_at': datetime.now().isoformat(),
        'description': 'Proposed verified candidate questions for Tamil Nadu State Board (Classes 6-12)',
        'safety_mode': 'DRY_RUN_ONLY_NO_DB_MODIFICATIONS',
        'total_verified_ready_for_import': len(verified_candidates),
        'manifest_sample': verified_candidates[:10],
        'candidates_by_class': {},
        'candidates_by_subject': {},
        'candidates_by_marks': {1.0: 0, 2.0: 0, 3.0: 0, 5.0: 0},
        'candidates_by_language': {'English': 0, 'Tamil': 0}
    }

    for vc in verified_candidates:
        cg = vc['class_grade']
        sb = vc['subject']
        mk = vc['marks']
        lg = vc['language']

        manifest['candidates_by_class'][cg] = manifest['candidates_by_class'].get(cg, 0) + 1
        manifest['candidates_by_subject'][sb] = manifest['candidates_by_subject'].get(sb, 0) + 1
        manifest['candidates_by_marks'][mk] = manifest['candidates_by_marks'].get(mk, 0) + 1
        manifest['candidates_by_language'][lg] = manifest['candidates_by_language'].get(lg, 0) + 1

    from collections import Counter
    rejection_counter = Counter([r['reason'] for r in rejected_candidates])
    review_counter = Counter()
    for n in needs_review_candidates:
        for r in n['reasons']:
            review_counter[r] += 1

    dry_run_summary = {
        'dry_run_timestamp': datetime.now().isoformat(),
        'database_inspected': db_path,
        'live_baseline': {
            'total_questions': initial_q_count,
            'total_users': initial_u_count,
            'total_generated_papers': initial_p_count,
            'live_tnsb_questions': len(live_tnsb_rows),
            'live_tnsb_1m_questions': sum(1 for r in live_tnsb_rows if r[3] == 1.0)
        },
        'validation_totals': {
            'total_candidates_analyzed': total_candidates,
            'verified_ready_to_import': len(verified_candidates),
            'needs_review_quarantined': len(needs_review_candidates),
            'rejected_count': len(rejected_candidates),
            'duplicate_collisions_filtered': len(duplicate_records),
            'rejection_reasons': dict(rejection_counter),
            'needs_review_reasons': dict(review_counter)
        },
        'projected_post_import': {
            'projected_tnsb_questions': len(live_tnsb_rows) + len(verified_candidates),
            'projected_tnsb_1m_questions': sum(1 for r in live_tnsb_rows if r[3] == 1.0) + manifest['candidates_by_marks'][1.0],
            'overwritten_live_records': 0,
            'status': 'READY_AWAITING_EXPLICIT_USER_CONFIRMATION'
        }
    }

    # Verify DB size and mtime are 100% UNCHANGED
    final_stat = os.stat(db_path)
    assert final_stat.st_size == initial_size, "CRITICAL: DB size modified during dry run!"
    assert final_stat.st_mtime == initial_mtime, "CRITICAL: DB mtime modified during dry run!"

    # Save Reports
    rep_dir = os.path.join(backend_dir, 'reports')
    os.makedirs(rep_dir, exist_ok=True)

    with open(os.path.join(rep_dir, 'full_curriculum_validation_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    with open(os.path.join(rep_dir, 'full_curriculum_dry_run_report.json'), 'w', encoding='utf-8') as f:
        json.dump(dry_run_summary, f, indent=2, ensure_ascii=False)

    with open(os.path.join(rep_dir, 'classes_6_to_12_coverage_matrix.json'), 'w', encoding='utf-8') as f:
        json.dump({'total_chapters': total_chapters_configured, 'pairs': matrix_rows}, f, indent=2, ensure_ascii=False)

    print("SUCCESS: Full Curriculum Validation & Dry Run Completed (100% Read-Only).")
    print(f"Total Candidates: {total_candidates}")
    print(f"Verified Ready: {len(verified_candidates)}")
    print(f"Needs Review: {len(needs_review_candidates)}")
    print(f"Rejected: {len(rejected_candidates)}")
    print(f"Duplicates / Collisions Filtered: {len(duplicate_records)}")
    print(f"Live DB File Size Unchanged: {final_stat.st_size} bytes")

if __name__ == '__main__':
    run_full_validation_and_dry_run()
