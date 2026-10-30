"""
ExamForge AI - Reusable Multi-Standard Textbook Question Extractor (v2 Quality Engine)
Supports Tamil Nadu State Board Textbooks across Classes 6, 7, 8, 9, 10, 11, and 12
for both Tamil Medium and English Medium, across all subjects.

Extraction Improvements in v2:
1. Pure question stem isolation: separates stems, options, answer keys, exercise instructions, and chapter headings.
2. Prevents composite exercise merges by strictly flushing on markdown headings and activity cues.
3. Accurate subject classification: resolves specific subjects (Biochemistry, Business Maths, Vocational Engineering)
   without partial substring collisions.
4. Strict type and marks consistency: eliminates invalid combinations (e.g. short_answer with 1 mark);
   marks are assigned only when supported by source structure, otherwise null.
5. Preserves original wording, Tamil Unicode NFC, and flags uncertain candidates with explicit audit reasons.
"""

import os
import re
import json
import csv
import logging
import unicodedata
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TextbookExtractorV2")

STANDARD_DIR_MAP = {
    '6th-standard': 'Class 6',
    '7th-standard': 'Class 7',
    '8th-standard': 'Class 8',
    '9th-standard': 'Class 9',
    '10th-standard': 'Class 10',
    '11th-standard': 'Class 11',
    '12th-standard': 'Class 12',
}

# Exclusion patterns: Non-evaluative sections, classroom activities, teacher instructions
EXCLUSION_KEYWORDS_TAMIL = [
    'கற்பவை கற்றபின்', 'நூல் வெளி', 'தெரிந்து தெளிவோம்', 'பாடலின் பொருள்',
    'உரைநடை உலகம்', 'கற்கண்டு', 'விரிவானம்', 'எடுத்துக்காட்டு',
    'செயல்பாடு', 'பாடச்சுருக்கம்', 'கலைச்சொற்கள்', 'கலைச்சொல் அறிவோம்',
    'நினைவில் கொள்க', 'பொருளடக்கம்', 'முகவுரை', 'நாட்டுப்பண்',
    'கற்றல் நோக்கங்கள்', 'கற்றலின் நோக்கங்கள்', 'மொழியோடு விளையாடு',
    'கட்டுரை எழுதுக', 'நயம் பாராட்டுக', 'அகராதியில் காண்க', 'காட்சியைக் கண்டு',
    'செயல் திட்டம்', 'நிற்க அதற்குத் தக', 'வாழ்வியல்'
]

EXCLUSION_KEYWORDS_ENGLISH = [
    'learning objectives', 'points to remember', 'solved problems', 'example',
    'activity', 'summary', 'glossary', 'table of contents', 'preface',
    'qr code', 'acknowledgement', 'project work', 'life skills', 'value corner',
    'fun with words', 'listening skill', 'speaking skill', 'case study'
]

def normalize_text(text: str) -> str:
    """Normalize Tamil and English text: NFC, strip ZWNJ, ZWSP, BOM."""
    if not text:
        return ""
    text = text.replace('\u200c', '').replace('\u200b', '').replace('\ufeff', '')
    return unicodedata.normalize('NFC', text).strip()

def resolve_subject(filename: str, rel_path: str) -> str:
    """Accurately determine subject without substring collisions."""
    # Check specific vocational and specialized subjects first
    if 'Bio_Chemistry' in filename:
        return 'Biochemistry'
    if 'Business_Mathematics' in filename or 'Business_Maths' in filename:
        return 'Business Mathematics & Statistics'
    if 'Basic_Automobile_Engineering' in filename:
        return 'Automobile Engineering'
    if 'Basic_Civil_Engineering' in filename:
        return 'Civil Engineering'
    if 'Basic_Electrical_Engineering' in filename:
        return 'Electrical Engineering'
    if 'Basic_Electronics_Engineering' in filename:
        return 'Electronics Engineering'
    if 'Basic_Mechanical_Engineering' in filename:
        return 'Mechanical Engineering'
    if 'Computer_Applications' in filename:
        return 'Computer Applications'
    if 'Computer_Science' in filename:
        return 'Computer Science'
    if 'General_Nursing' in filename or 'Nursing' in filename:
        return 'General Nursing'
    if 'Agricultural_Science' in filename:
        return 'Agricultural Science'
    if 'Nutrition_and_Dietetics' in filename or 'Nutrition' in filename:
        return 'Nutrition & Dietetics'
    if 'Textiles_and_Dress_Designing' in filename:
        return 'Textiles & Dress Designing'
    if 'Food_Service_Management' in filename:
        return 'Food Service Management'
    if 'Employability_Skills' in filename:
        return 'Employability Skills'
    if 'Communicative_English' in filename or 'Communicative' in filename:
        return 'Communicative English'
    if 'Bio_Botany' in filename or 'Botany' in filename:
        return 'Botany'
    if 'Bio_Zoology' in filename or 'Zoology' in filename:
        return 'Zoology'
    if 'Biology' in filename:
        return 'Biology'
    if 'Physics' in filename:
        return 'Physics'
    if 'Chemistry' in filename:
        return 'Chemistry'
    if 'Social_Science' in filename or 'Social' in filename:
        return 'Social Science'
    if 'Science_and_Social_Science' in filename:
        return 'Science & Social Science'
    if 'Science' in filename:
        return 'Science'
    if 'Mathematics' in filename or 'Maths' in filename:
        return 'Mathematics'
    if 'Tamil' in filename:
        return 'Tamil'
    if 'English' in filename and not 'English_Medium' in filename.replace('Class_10_English', '').replace('Class_6_English', ''):
        return 'English'
    if 'Accountancy' in filename:
        return 'Accountancy'
    if 'Commerce' in filename:
        return 'Commerce'
    if 'Economics' in filename:
        return 'Economics'
    if 'Geography' in filename:
        return 'Geography'
    if 'History' in filename:
        return 'History'
    if 'Auditing' in filename:
        return 'Auditing'
    if 'Statistics' in filename:
        return 'Statistics'
    if 'Political_Science' in filename:
        return 'Political Science'

    # Fallback from regex
    m = re.match(r'Class_\d+_(.+?)(?:_Tamil|_English|_Medium|_\-_)', filename)
    if m:
        return m.group(1).replace('_', ' ').strip()
    return 'General'

def parse_file_metadata(rel_path: str, filename: str) -> Dict[str, str]:
    """Extract standard, subject, medium, edition, and term from relative path."""
    normalized_rel = rel_path.replace('/', os.sep).replace('\\', os.sep)
    parts = normalized_rel.split(os.sep)
    std_folder = parts[0]
    class_grade = STANDARD_DIR_MAP.get(std_folder, std_folder)
    
    folder_medium = parts[1] if len(parts) > 1 else 'Unknown'
    if 'Tamil_Medium' in filename or 'Tamil_Tamil' in filename or folder_medium == 'Tamil':
        medium = 'Tamil'
    elif 'English_Medium' in filename or 'English_English' in filename or folder_medium == 'English':
        medium = 'English'
    else:
        medium = folder_medium

    ed_m = re.search(r'(202[45])_Edition', filename)
    edition = f"{ed_m.group(1)}_Edition" if ed_m else "Unknown"

    tm = re.search(r'Term[_\s\-]+([123])', filename, re.I)
    term = f"Term {tm.group(1)}" if tm else "Full Year"

    subj = resolve_subject(filename, rel_path)

    return {
        'class_grade': class_grade,
        'subject': subj,
        'medium': medium,
        'edition': edition,
        'term': term
    }

def separate_answer_text(text: str) -> Tuple[str, Optional[str]]:
    """Separate trailing or inline answer text from question stem."""
    if not text:
        return "", None
    
    clean_stem = text
    ans_text = None

    # Check for parenthesized answer blocks with balanced parentheses
    for kw in ['(Answer', '(Answers', '(விடை', '(தீர்வு', '(Solution', '[Answer', '[விடை']:
        idx = clean_stem.find(kw)
        if idx != -1:
            open_ch = clean_stem[idx]
            close_ch = ')' if open_ch == '(' else ']'
            depth = 0
            end_idx = -1
            for i in range(idx, len(clean_stem)):
                if clean_stem[i] == open_ch:
                    depth += 1
                elif clean_stem[i] == close_ch:
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
            if end_idx != -1:
                ans_raw = clean_stem[idx+1:end_idx-1]
                ans_text = re.sub(r'^(?:Answer|Answers|விடை|தீர்வு|Solution)[:\-–\s]*', '', ans_raw, flags=re.I).strip()
                trailing_explanation = clean_stem[end_idx:].strip()
                if ans_text in ['A', 'B', 'C', 'D', 'a', 'b', 'c', 'd', 'அ', 'ஆ', 'இ', 'ஈ', '1', '2', '3', '4']:
                    if trailing_explanation:
                        ans_text = f"{ans_text}: {trailing_explanation}"
                        clean_stem = clean_stem[:idx].strip()
                    else:
                        clean_stem = (clean_stem[:idx] + ' ' + clean_stem[end_idx:]).strip()
                else:
                    clean_stem = (clean_stem[:idx] + ' ' + clean_stem[end_idx:]).strip()
                clean_stem = re.sub(r'\s+', ' ', clean_stem)
                break
    
    ans_patterns = [
        # (Answer B) explanation... at end
        r'(?:(?:\(|\[)\s*(?:விடை|Answer|Answers|Ans|தீர்வு|Solution)\s*[:\-–\)]?\s*([A-Da-d1-4அ-ஈ])\s*(?:\)|\])\s*(.*)$)',
        # Answer: B or விடை : ஆ at end
        r'(?:(?:\(|\[)?\s*(?:விடை|Answer|Answers|Ans|தீர்வு|Solution)\s*[:\-–\)]\s*(.+?)(?:\)|\])?$)',
        r'(?:(?:விடை|தீர்வு)\s*[:\-–]\s*(.*)$)',
        r'(?:(?:Answer|Answers|Solution|Ans)\s*[:\-–]\s*(.*)$)',
    ]
    
    for pat in ans_patterns:
        m = re.search(pat, clean_stem, re.IGNORECASE)
        if m:
            if not ans_text:
                if len(m.groups()) == 2 and m.group(1) and m.group(2):
                    ans_text = f"{m.group(1)}: {m.group(2).strip()}"
                elif m.group(1):
                    ans_text = m.group(1).strip()
            clean_stem = clean_stem[:m.start()].strip()
            break
            
    return clean_stem, ans_text

def separate_inline_options(stem: str) -> Tuple[str, List[Dict[str, str]]]:
    """Parse inline choices (e.g. அ. opt1 ஆ. opt2 ...) if present inside stem."""
    options = []
    # Check for Tamil inline options: அ. / அ) ... ஆ. ... இ. ... ஈ. ...
    tam_inline = list(re.finditer(r'(?:^|\s+)([அஆஇஈ])[\.\,\)]\s*', stem))
    if len(tam_inline) >= 3:
        clean_stem = stem[:tam_inline[0].start()].strip()
        for i, match in enumerate(tam_inline):
            lbl = match.group(1)
            start_pos = match.end()
            end_pos = tam_inline[i+1].start() if i + 1 < len(tam_inline) else len(stem)
            opt_text = stem[start_pos:end_pos].strip()
            options.append({'label': lbl, 'text': opt_text})
        return clean_stem, options

    # Check for English inline options: (a) / A. ... B. ... C. ... D. ...
    eng_inline = list(re.finditer(r'(?:^|\s+)(?:\(?([A-Da-d])[\.\)]|\(([A-Da-d])\))\s*', stem))
    if len(eng_inline) >= 3:
        clean_stem = stem[:eng_inline[0].start()].strip()
        for i, match in enumerate(eng_inline):
            lbl = (match.group(1) or match.group(2)).upper()
            start_pos = match.end()
            end_pos = eng_inline[i+1].start() if i + 1 < len(eng_inline) else len(stem)
            opt_text = stem[start_pos:end_pos].strip()
            options.append({'label': lbl, 'text': opt_text})
        return clean_stem, options

    return stem, options


class TextbookExtractor:
    """Multi-standard candidate question extraction engine (v2)."""

    def __init__(self, base_staging_dir: str, output_candidates_dir: str):
        self.base_staging_dir = base_staging_dir
        self.output_candidates_dir = output_candidates_dir
        os.makedirs(self.output_candidates_dir, exist_ok=True)

    def extract_file(self, full_path: str, rel_path: str) -> List[Dict[str, Any]]:
        filename = os.path.basename(full_path)
        meta = parse_file_metadata(rel_path, filename)
        
        candidates: List[Dict[str, Any]] = []
        
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line.rstrip('\r\n') for line in f]

        current_unit = "General"
        in_evaluation_mode = False
        current_section_type = None  # 'mcq', 'fill', 'match', 'short', 'medium', 'long'
        current_section_heading = ""
        current_exercise_instruction = ""
        
        # Buffer for parsing individual questions, options, and answers
        current_q_stem: List[str] = []
        current_q_options: List[Dict[str, str]] = []
        current_q_answer: Optional[str] = None
        current_q_line_start = 0
        current_q_type = "short_answer"
        current_q_marks = None
        
        def flush_question():
            nonlocal current_q_stem, current_q_options, current_q_answer, current_q_line_start, current_q_type, current_q_marks
            if not current_q_stem:
                return
            raw_text = " ".join([s.strip() for s in current_q_stem if s.strip()]).strip()
            # Clean leading number, bullet, or asterisk
            raw_text = re.sub(r'^(?:\d+[\.\)\-]?|\-|\*)\s*', '', raw_text).strip()
            
            # Skip empty or trivial snippets
            if len(raw_text) < 6:
                current_q_stem, current_q_options, current_q_answer = [], [], None
                return

            # Separate trailing or inline answer text from stem
            clean_stem, extracted_ans = separate_answer_text(raw_text)
            final_ans = current_q_answer or extracted_ans

            # Check if options are embedded inline inside the stem
            clean_stem, inline_options = separate_inline_options(clean_stem)
            final_options = current_q_options if current_q_options else inline_options

            # If options were found inline or under an MCQ header, classify as objective
            if final_options and len(final_options) >= 2:
                current_q_type = "objective"
                current_q_marks = 1

            # Strict Marks & Type Consistency Enforcement
            if current_q_type == "objective":
                final_marks = 1
            elif current_q_type == "short_answer":
                final_marks = 2 if current_section_type == 'short' else None
            elif current_q_type == "medium_answer":
                final_marks = 3 if current_section_type == 'medium' else None
            elif current_q_type == "long_answer":
                final_marks = 5 if current_section_type == 'long' else None
            else:
                final_marks = None

            # Validation status & uncertainty flagging
            val_status = "candidate_review"
            unc_reasons = []

            # Flag composite or merged exercise passages (> 320 chars or containing activity/table artifacts)
            if len(clean_stem) > 320 or '####' in clean_stem or '| --- |' in clean_stem:
                val_status = "uncertain"
                unc_reasons.append("Composite exercise block or multi-instruction passage")

            # Flag MCQ with insufficient options
            if current_q_type == "objective" and current_section_type == 'mcq' and len(final_options) < 2:
                val_status = "uncertain"
                unc_reasons.append(f"MCQ section had {len(final_options)} option(s) detected")

            # Flag subject conflict if question text mentions cell membrane in Chemistry
            if meta['subject'] == 'Chemistry' and any(k in clean_stem.lower() for k in ['cell membrane', 'செல் சவ்வு']):
                val_status = "uncertain"
                unc_reasons.append("Potential subject conflict: biological content in Chemistry")

            cand_id = f"CAND_{meta['class_grade'].replace(' ', '')}_{meta['subject'][:3].upper()}_{len(candidates)+1:04d}"
            
            candidates.append({
                'candidate_id': cand_id,
                'class_grade': meta['class_grade'],
                'subject': meta['subject'],
                'medium': meta['medium'],
                'term': meta['term'],
                'edition': meta['edition'],
                'source_file': rel_path.replace('\\', '/'),
                'source_line_start': current_q_line_start,
                'chapter_heading': current_unit,
                'section_heading': current_section_heading,
                'exercise_instruction': current_exercise_instruction,
                'question_type': current_q_type,
                'suggested_marks': final_marks,
                'bloom_level': None,  # Ground truth not fabricated
                'question_text': clean_stem,
                'options': final_options,
                'answer_text': final_ans,
                'validation_status': val_status,
                'uncertainty_reason': "; ".join(unc_reasons) if unc_reasons else ""
            })
            
            current_q_stem = []
            current_q_options = []
            current_q_answer = None
            current_q_line_start = 0

        # Option parsing regexes
        tam_opt_pat = re.compile(r'^(?:([அஆஇஈ])[\,\.\)]|\(([அஆஇஈ])\))\s*(.+)$')
        eng_opt_pat = re.compile(r'^(?:([a-dA-D1-4])[\)\.]|\(([a-dA-D1-4])\))\s*(.+)$')
        
        unit_tam_pat = re.compile(r'^(?:#+\s*)?(?:இயல்|அலகு)\s*([0-9\u0b80-\u0bff]+)\s*[:\-–]?\s*(.*)$')
        unit_eng_pat = re.compile(r'^(?:#+\s*)?(?:Unit|Chapter)\s*(\d+)\s*[:\-–]?\s*(.*)$', re.I)

        for line_idx, raw_line in enumerate(lines, 1):
            line = normalize_text(raw_line)
            if not line:
                continue

            # 1. Any Markdown heading (#+) flushes the current question stem
            if line.startswith('#'):
                flush_question()

            # 2. Check Unit / Chapter change
            m_tam_u = unit_tam_pat.match(line)
            if m_tam_u and len(line) < 100:
                flush_question()
                current_unit = f"Unit {m_tam_u.group(1)}: {m_tam_u.group(2)}".strip()
                in_evaluation_mode = False
                continue
                
            m_eng_u = unit_eng_pat.match(line)
            if m_eng_u and len(line) < 100:
                flush_question()
                current_unit = f"Unit {m_eng_u.group(1)}: {m_eng_u.group(2)}".strip()
                in_evaluation_mode = False
                continue

            # 3. Check Exclusions & Classroom Activities (strict boundary)
            line_lower = line.lower()
            if any(k in line for k in EXCLUSION_KEYWORDS_TAMIL) or any(k in line_lower for k in EXCLUSION_KEYWORDS_ENGLISH):
                flush_question()
                in_evaluation_mode = False
                current_section_type = None
                continue

            # 4. Check Evaluation Headings
            line_clean_eval = line.replace('#', '').strip()
            line_clean_lower = line_clean_eval.lower()
            
            # Check MCQ headings (1 mark)
            if any(k in line_clean_eval for k in ['பலவுள் தெரிக', 'சரியான விடையைத் தேர்ந்தெடு', 'பன்முகத் தெரிவு']) or \
               any(k in line_clean_lower for k in ['choose the correct answer', 'choose the best answer', 'multiple choice questions']):
                flush_question()
                in_evaluation_mode = True
                current_section_type = 'mcq'
                current_section_heading = line_clean_eval
                current_exercise_instruction = line_clean_eval
                continue

            # Check Fill in the blanks (1 mark)
            if any(k in line_clean_eval for k in ['கோடிட்ட இடங்களை', 'கோடிட்ட இடத்தை']) or \
               any(k in line_clean_lower for k in ['fill in the blanks', 'fill in the blank']):
                flush_question()
                in_evaluation_mode = True
                current_section_type = 'fill'
                current_section_heading = line_clean_eval
                current_exercise_instruction = line_clean_eval
                continue

            # Check Match the following / True or False (1 mark)
            if any(k in line_clean_eval for k in ['பொருத்துக', 'சரியா அல்லது தவறா', 'சரியா தவறா']) or \
               any(k in line_clean_lower for k in ['match the following', 'true or false', 'state true or false']):
                flush_question()
                in_evaluation_mode = True
                current_section_type = 'match'
                current_section_heading = line_clean_eval
                current_exercise_instruction = line_clean_eval
                continue

            # Check Short Answer / 2 marks
            if any(k in line_clean_eval for k in ['குறுவினா', 'சுருக்கமாக விடையளி', 'ஓரிரு சொற்களில்']) or \
               any(k in line_clean_lower for k in ['answer in one or two sentences', 'very short answer', 'answer briefly', 'short answer questions']):
                flush_question()
                in_evaluation_mode = True
                current_section_type = 'short'
                current_section_heading = line_clean_eval
                current_exercise_instruction = line_clean_eval
                continue

            # Check Medium Answer / 3-4 marks
            if any(k in line_clean_eval for k in ['சிறுவினா', 'வேறுபடுத்துக', 'காரணம் கூறுக']) or \
               any(k in line_clean_lower for k in ['distinguish between', 'give reasons', 'brief answer questions']):
                flush_question()
                in_evaluation_mode = True
                current_section_type = 'medium'
                current_section_heading = line_clean_eval
                current_exercise_instruction = line_clean_eval
                continue

            # Check Long Answer / 5 marks
            if any(k in line_clean_eval for k in ['நெடுவினா', 'விரிவாக விடையளி', 'விரிவான விடையளி']) or \
               any(k in line_clean_lower for k in ['answer in detail', 'long answer questions', 'paragraph questions', 'essay questions']):
                flush_question()
                in_evaluation_mode = True
                current_section_type = 'long'
                current_section_heading = line_clean_eval
                current_exercise_instruction = line_clean_eval
                continue

            # Generic evaluation parent heading
            if any(k in line_clean_eval for k in ['மதிப்பீடு', 'மதிப்பிடுதல்', 'வினாக்கள்']) or \
               any(k in line_clean_lower for k in ['textbook evaluation', 'textbook exercises', 'evaluation', 'exercises', 'self evaluation']):
                flush_question()
                in_evaluation_mode = True
                current_section_heading = line_clean_eval
                continue

            # If not currently in evaluation mode, skip text (preserves distinction from lesson text)
            if not in_evaluation_mode:
                continue

            # 5. Check if the line is an Answer key line
            clean_stem_temp, found_ans = separate_answer_text(line)
            if found_ans and not clean_stem_temp:
                current_q_answer = found_ans
                continue

            # 6. Parse Options if inside MCQ mode
            if current_section_type == 'mcq' and current_q_stem:
                m_opt_tam = tam_opt_pat.match(line)
                if m_opt_tam:
                    lbl = m_opt_tam.group(1) or m_opt_tam.group(2)
                    opt_txt = m_opt_tam.group(3).strip()
                    # Check if answer key is appended to option text
                    opt_clean, opt_ans = separate_answer_text(opt_txt)
                    if opt_ans:
                        current_q_answer = opt_ans
                    current_q_options.append({'label': lbl, 'text': opt_clean})
                    continue
                    
                m_opt_eng = eng_opt_pat.match(line)
                if m_opt_eng:
                    lbl = (m_opt_eng.group(1) or m_opt_eng.group(2)).upper()
                    opt_txt = m_opt_eng.group(3).strip()
                    opt_clean, opt_ans = separate_answer_text(opt_txt)
                    if opt_ans:
                        current_q_answer = opt_ans
                    current_q_options.append({'label': lbl, 'text': opt_clean})
                    continue

                # Bullet-style options in markdown (- option text)
                if line.startswith('- ') and len(current_q_options) < 4:
                    bullet_txt = line[2:].strip()
                    if len(bullet_txt) < 80 and not bullet_txt.endswith('?'):
                        lbl = chr(65 + len(current_q_options))  # A, B, C, D
                        opt_clean, opt_ans = separate_answer_text(bullet_txt)
                        if opt_ans:
                            current_q_answer = opt_ans
                        current_q_options.append({'label': lbl, 'text': opt_clean})
                        continue

            # 7. Check New Question Trigger
            is_new_q = False
            num_m = re.match(r'^(?:(?:\d+|வினா\s*எண்\s*\d+)[\.\:\)\s]+|\-\s+)(.+)$', line)
            if num_m:
                stem_candidate = num_m.group(1).strip()
                if not tam_opt_pat.match(line) and not eng_opt_pat.match(line):
                    is_new_q = True

            if is_new_q:
                flush_question()
                current_q_line_start = line_idx
                current_q_stem.append(line)
                
                # Determine initial question type
                if current_section_type in ['mcq', 'fill', 'match']:
                    current_q_type = 'objective'
                elif current_section_type == 'short':
                    current_q_type = 'short_answer'
                elif current_section_type == 'medium':
                    current_q_type = 'medium_answer'
                elif current_section_type == 'long':
                    current_q_type = 'long_answer'
                else:
                    current_q_type = 'short_answer'
                continue

            # 8. Continuing ongoing question stem
            if current_q_stem:
                if line.startswith('> [Image:') or line.startswith('| ---'):
                    continue
                if not tam_opt_pat.match(line) and not eng_opt_pat.match(line):
                    current_q_stem.append(line)

        # Flush trailing question
        flush_question()
        return candidates

    def run_all(self, standards: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run extraction across all specified standards and save staging artifacts."""
        if standards is None:
            standards = list(STANDARD_DIR_MAP.keys())

        all_candidates: List[Dict[str, Any]] = []
        files_inspected = 0
        file_summary: List[Dict[str, Any]] = []

        for std in standards:
            std_path = os.path.join(self.base_staging_dir, std)
            if not os.path.exists(std_path):
                logger.warning(f"Standard directory not found: {std_path}")
                continue

            for root, _, files in os.walk(std_path):
                for f in sorted(files):
                    if f.endswith('.md'):
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, self.base_staging_dir)
                        try:
                            file_candidates = self.extract_file(full_p, rel_p)
                            all_candidates.extend(file_candidates)
                            files_inspected += 1
                            meta = parse_file_metadata(rel_p, f)
                            file_summary.append({
                                'file': rel_p.replace('\\', '/'),
                                'class_grade': meta['class_grade'],
                                'subject': meta['subject'],
                                'medium': meta['medium'],
                                'candidates_extracted': len(file_candidates),
                                'verified_mcqs': sum(1 for c in file_candidates if c['question_type'] == 'objective' and len(c['options']) >= 2),
                                'short_answers': sum(1 for c in file_candidates if c['question_type'] == 'short_answer'),
                                'long_answers': sum(1 for c in file_candidates if c['question_type'] == 'long_answer'),
                            })
                        except Exception as e:
                            logger.error(f"Error extracting from {rel_p}: {e}")

        # Save artifacts to versioned output directory
        json_out = os.path.join(self.output_candidates_dir, "candidates_all_standards.json")
        csv_out = os.path.join(self.output_candidates_dir, "candidates_all_standards.csv")
        
        with open(json_out, 'w', encoding='utf-8') as f:
            json.dump(all_candidates, f, ensure_ascii=False, indent=2)

        # Write CSV with complete schema
        fieldnames = [
            'candidate_id', 'class_grade', 'subject', 'medium', 'term', 'edition',
            'chapter_heading', 'section_heading', 'exercise_instruction',
            'question_type', 'suggested_marks', 'bloom_level', 'question_text',
            'answer_text', 'validation_status', 'uncertainty_reason',
            'source_file', 'source_line_start'
        ]
        with open(csv_out, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for cand in all_candidates:
                writer.writerow(cand)

        # Standard-specific breakdown CSVs
        for std_key, class_name in STANDARD_DIR_MAP.items():
            class_cands = [c for c in all_candidates if c['class_grade'] == class_name]
            class_csv = os.path.join(self.output_candidates_dir, f"candidates_{class_name.lower().replace(' ', '_')}.csv")
            with open(class_csv, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                for cand in class_cands:
                    writer.writerow(cand)

        # Generate aggregated stats
        stats: Dict[str, Any] = {
            'total_files_inspected': files_inspected,
            'total_candidates_extracted': len(all_candidates),
            'by_class': defaultdict(int),
            'by_subject': defaultdict(int),
            'by_medium': defaultdict(int),
            'by_question_type': defaultdict(int),
            'by_marks': defaultdict(int),
            'by_validation_status': defaultdict(int),
        }
        for c in all_candidates:
            stats['by_class'][c['class_grade']] += 1
            stats['by_subject'][c['subject']] += 1
            stats['by_medium'][c['medium']] += 1
            stats['by_question_type'][c['question_type']] += 1
            marks_str = str(c['suggested_marks']) if c['suggested_marks'] is not None else "None"
            stats['by_marks'][marks_str] += 1
            stats['by_validation_status'][c['validation_status']] += 1

        stats_json = os.path.join(self.output_candidates_dir, "coverage_report.json")
        with open(stats_json, 'w', encoding='utf-8') as f:
            json.dump({
                'stats': {k: dict(v) if isinstance(v, defaultdict) else v for k, v in stats.items()},
                'files': file_summary
            }, f, ensure_ascii=False, indent=2)

        return {
            'stats': stats,
            'file_summary': file_summary,
            'total_candidates': len(all_candidates),
            'output_json': json_out,
            'output_csv': csv_out
        }
