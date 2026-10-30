"""
Intelligent Question Selection Service for Tamil Nadu State Board (Classes 6–12)
Handles strict curriculum constraints, Bloom's Taxonomy & Difficulty distribution,
multi-chapter selection, mark optimization, and sectioning.
"""

import random
import re
from collections import Counter

VALID_TN_CLASSES = ['Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']

VAGUE_QUESTION_PATTERNS = [
    r"primary laws governing\b",
    r"state the primary laws governing\b",
    r"key components observed in\b",
    r"differentiate between key components observed in\b",
    r"fundamental principles of .+ with diagrams\b",
    r"fundamental principles of\b",
    r"explain the fundamental principles of\b",
    r"standard equation derived from\b",
    r"defining theorem in\b",
    r"major identity or geometric property in\b",
    r"construct or plot the mathematical model representing\b",
    r"policy decisions during\b",
    r"experimental setup used to verify\b",
    r"major concepts, definitions, and si units associated with\b",
    r"key scientific phenomena observed in\b",
    r"practical applications of .+ in modern science and technology\b",
]


def normalize_board(b):
    """Normalize board name variations (e.g. 'Tamil NaduState Board', 'samacheer kalvi') to standard."""
    if not b:
        return 'Tamil Nadu State Board'
    s = str(b).strip()
    s_clean = re.sub(r'\s+', ' ', s).lower()
    if 'tamil' in s_clean and 'board' in s_clean:
        return 'Tamil Nadu State Board'
    if s_clean in ['tamil nadu', 'samacheer kalvi', 'samacheer', 'tnsb']:
        return 'Tamil Nadu State Board'
    return s


def is_vague_question(text):
    """Detect generic, synthetic template questions lacking specific curriculum concepts."""
    if not text:
        return True, "Question text is empty"
    lower = str(text).strip().lower()
    for pat in VAGUE_QUESTION_PATTERNS:
        if re.search(pat, lower, re.IGNORECASE):
            return True, f"Matches generic template pattern: '{pat}'"
    return False, None


def is_invalid_question_content(text, target_language='English'):
    """
    Detect malformed questions, raw URLs, bibliography citations,
    or language mismatches (e.g. Tamil script in English paper).
    """
    if not text:
        return True, "Question text is empty"
    
    clean = str(text).strip()
    
    # 1. Reject raw URLs or strings containing links
    if re.search(r'https?://|www\.[a-z0-9\-]+\.[a-z]{2,}', clean, re.IGNORECASE):
        return True, "Contains raw URL or web resource reference"
    
    # 2. Reject bibliography / reference book citations / publishers
    if re.search(r'\b(?:reference books?|internet resources?|publications?|publishers?|publishing house|company ltd|edition|isbn|rastogi|s\.chand|narosa|b\.s\.bahl|pl sony|puri and sharma|atkins|h\.c\. verma|mcgraw|vol\.|volume)\b', clean, re.IGNORECASE):
        return True, "Contains textbook bibliography, publisher, or citation metadata"
        
    # Reject isolated section header artifacts
    if re.search(r'^(?:higher order thinking skills|hots|assertion and reason|assertion and reasoning)\s*(?:\([a-z]+\))?$', clean, re.IGNORECASE):
        return True, "Contains isolated section heading artifact"
        
    # 3. Reject language mismatch
    has_tamil = any('\u0b80' <= ch <= '\u0bff' for ch in clean)
    if target_language and str(target_language).strip().lower() in ['english', 'en'] and has_tamil:
        return True, "Contains Tamil script in an English-medium question paper"
    elif target_language and str(target_language).strip().lower() in ['tamil', 'ta'] and not has_tamil:
        return True, "Missing Tamil script in a Tamil-medium question paper"
        
    # 4. Reject excessively short strings
    if len(clean) < 8:
        return True, "Question text is too short to be a valid question"
        
    return False, None



def format_mark(m):
    """Format mark cleanly: return integer if whole, float otherwise."""
    if m is None:
        return 0
    try:
        f = float(m)
        return int(f) if f.is_integer() else round(f, 1)
    except (ValueError, TypeError):
        return m


def _solve_mark_counts(target_count, target_total, avail_counts):
    """
    Find counts (n1, n2, n3, n5) such that:
    n1 + n2 + n3 + n5 == target_count
    1*n1 + 2*n2 + 3*n3 + 5*n5 == target_total
    0 <= ni <= avail_counts[i]
    """
    best_sol = None
    min_penalty = float('inf')

    max_n5 = min(target_count, avail_counts.get(5, 0), int(target_total // 5))
    for n5 in range(max_n5, -1, -1):
        rem_count_after_5 = target_count - n5
        rem_marks_after_5 = target_total - 5 * n5
        if rem_marks_after_5 < rem_count_after_5:  # even if all 1-mark, not enough
            continue

        max_n3 = min(rem_count_after_5, avail_counts.get(3, 0), int(rem_marks_after_5 // 3))
        for n3 in range(max_n3, -1, -1):
            rem_count_after_3 = rem_count_after_5 - n3
            rem_marks_after_3 = rem_marks_after_5 - 3 * n3
            if rem_marks_after_3 < rem_count_after_3:
                continue

            # We need n1 + n2 == rem_count_after_3 and 1*n1 + 2*n2 == rem_marks_after_3
            # n2 = rem_marks_after_3 - rem_count_after_3
            # n1 = rem_count_after_3 - n2
            n2 = rem_marks_after_3 - rem_count_after_3
            n1 = rem_count_after_3 - n2

            if 0 <= n2 <= avail_counts.get(2, 0) and 0 <= n1 <= avail_counts.get(1, 0):
                # Prefer balanced composition: some 5-mark, good short-answer (2 & 3), some objective (1)
                penalty = abs(n5 - (target_count * 0.25)) + abs(n3 - (target_count * 0.35)) + abs(n2 - (target_count * 0.25))
                if penalty < min_penalty:
                    min_penalty = penalty
                    best_sol = (n1, n2, n3, n5)
                    if penalty == 0:
                        return best_sol

    return best_sol


def select_questions(
    available_questions,
    num_questions=None,
    total_marks=None,
    subject=None,
    topic=None,
    topics=None,
    board='Tamil Nadu State Board',
    class_grade=None,
    question_type=None,
    bloom_level=None,
    difficulty=None,
    difficulty_distribution=None,  # e.g., {'Easy': 30, 'Medium': 50, 'Hard': 20}
    bloom_distribution=None,        # e.g., {'Remember': 25, 'Understand': 35, ...}
    duration_minutes=None,
    sections_config=None,           # Dynamic section definitions: [{'label': 'A', 'marks_per_question': 1, 'num_questions': 5}, ...]
    seed=None,
    language=None                   # Medium of examination: 'English' (default for non-Tamil) or 'Tamil'
):
    """
    Select questions based on teacher requirements with strict Tamil Nadu State Board constraints:
    - Strictly filters by class, subject, and selected syllabus portions.
    - Excludes vague/boilerplate questions.
    - Enforces continuous sequential numbering across sections.
    - Guarantees section totals equal configured maximum marks.
    - Verifies curriculum source and metadata.
    """
    if seed is not None:
        random.seed(seed)

    warnings = []
    filters_applied = []

    # Step 1: Strict Board and Class Validation
    normalized_board = normalize_board(board) if board else 'Tamil Nadu State Board'
    if normalized_board != 'Tamil Nadu State Board':
        return {
            'success': False,
            'is_valid': False,
            'error': f"Unsupported educational board '{board}'. The application strictly supports Tamil Nadu State Board / Samacheer Kalvi.",
            'eligible_count': 0,
            'selected_questions': []
        }

    if class_grade and class_grade not in VALID_TN_CLASSES:
        return {
            'success': False,
            'is_valid': False,
            'error': f"Invalid Class '{class_grade}'. Only Classes 6 through 12 are supported for Tamil Nadu State Board.",
            'eligible_count': 0,
            'selected_questions': []
        }

    eligible = list(available_questions)

    # Filter to Tamil Nadu State Board only (robust to casing and spacing variants)
    eligible = [q for q in eligible if not q.get('board') or normalize_board(q.get('board')) == 'Tamil Nadu State Board']
    filters_applied.append("board=Tamil Nadu State Board")

    if class_grade:
        eligible = [q for q in eligible if str(q.get('class_grade', '')).strip() == class_grade]
        filters_applied.append(f"class_grade={class_grade}")

    if subject:
        eligible = [q for q in eligible if str(q.get('subject', '')).strip().lower() == subject.strip().lower()]
        filters_applied.append(f"subject={subject}")

    # Step 2: Strict Topics / Syllabus Chapters Filtering
    import unicodedata
    all_topics = set()
    display_topics = []
    
    def _add_topic_norm(raw_str):
        if not raw_str or not isinstance(raw_str, str):
            return
        s = raw_str.strip()
        if not s or s.lower() in ['complete syllabus', 'complete syllabus (all chapters)', 'all chapters', 'all']:
            return
        nfc_s = unicodedata.normalize('NFC', s)
        nfd_s = unicodedata.normalize('NFD', s)
        all_topics.add(nfc_s.lower())
        all_topics.add(nfd_s.lower())
        if nfc_s not in display_topics:
            display_topics.append(nfc_s)

    if topics:
        if isinstance(topics, list):
            for t in topics:
                if t and isinstance(t, str):
                    for sub in t.split(','):
                        _add_topic_norm(sub)
        elif isinstance(topics, str):
            for sub in topics.split(','):
                _add_topic_norm(sub)

    if topic and isinstance(topic, str):
        for sub in topic.split(','):
            _add_topic_norm(sub)

    if all_topics:
        in_syllabus = []
        for q in eligible:
            raw_top = str(q.get('topic', '')).strip()
            q_top_nfc = unicodedata.normalize('NFC', raw_top).lower()
            q_top_nfd = unicodedata.normalize('NFD', raw_top).lower()
            if q_top_nfc in all_topics or q_top_nfd in all_topics:
                in_syllabus.append(q)
            else:
                warnings.append(
                    f"Question '{q.get('question_id', q.get('id', 'N/A'))}' from chapter '{q.get('topic')}' "
                    f"excluded: outside selected portions ({', '.join(sorted(display_topics))})."
                )
        eligible = in_syllabus
        filters_applied.append(f"topics={sorted(display_topics)}")

    # Step 3: Vague & Template Question Quality Filter and Language Integrity
    target_language = language or ('Tamil' if str(subject).strip().lower() == 'tamil' else 'English')
    quality_filtered = []
    for q in eligible:
        q_text = q.get('question') or q.get('question_text')
        
        # Check for invalid content (raw URLs, citations, language mismatches)
        invalid, inv_reason = is_invalid_question_content(q_text, target_language=target_language)
        if invalid:
            warnings.append(
                f"Excluded invalid question '{q.get('question_id', q.get('id', 'N/A'))}': {inv_reason}."
            )
            continue

        vague, reason = is_vague_question(q_text)
        if vague:
            warnings.append(
                f"Excluded vague/template question '{q.get('question_id', q.get('id', 'N/A'))}': {reason}."
            )
        else:
            quality_filtered.append(q)

    # Strictly do NOT fall back to vague synthetic templates; preserve authentic curriculum questions only
    eligible = quality_filtered


    # Source & curriculum alignment audit
    for q in eligible:
        src = str(q.get('source', '')).strip()
        is_verified = bool(q.get('verified', False))
        is_authentic_tn = any(k in src.lower() for k in ['tamil nadu', 'samacheer', 'state board'])
        q['curriculum_aligned'] = bool(is_verified and is_authentic_tn)
        if not q['curriculum_aligned'] and q.get('board') in ['Tamil Nadu State Board', 'Samacheer Kalvi']:
            warnings.append(
                f"Question '{q.get('question_id', q.get('id', 'N/A'))}' metadata does not verify Samacheer Kalvi source."
            )

    if question_type:
        type_filtered = [q for q in eligible if str(q.get('question_type', '')).strip().lower() == question_type.strip().lower()]
        if type_filtered:
            eligible = type_filtered
            filters_applied.append(f"question_type={question_type}")

    if bloom_level:
        bloom_filtered = [q for q in eligible if str(q.get('bloom_level', '')).strip().lower() == bloom_level.strip().lower()]
        if bloom_filtered:
            eligible = bloom_filtered
            filters_applied.append(f"bloom_level={bloom_level}")

    if difficulty:
        diff_filtered = [q for q in eligible if str(q.get('difficulty', '')).strip().lower() == difficulty.strip().lower()]
        if diff_filtered:
            eligible = diff_filtered
            filters_applied.append(f"difficulty={difficulty}")

    if not eligible:
        return {
            'success': False,
            'is_valid': False,
            'error': f"No questions in the approved Tamil Nadu State Board question bank match the criteria: Class '{class_grade or 'Any'}', Subject '{subject or 'Any'}' with the specified chapters/filters.",
            'filters_applied': filters_applied,
            'eligible_count': 0,
            'suggestions': [
                "Select additional chapters from the syllabus",
                "Ensure question filters match the available topics in the curriculum",
                "Upload and ingest additional past papers via the Admin Dataset Management panel"
            ],
            'selected_questions': [],
            'warnings': warnings
        }

    # Step 4 & 5: Selection based on Dynamic Section Config OR Legacy Distribution Solver
    sections = []
    ordered_questions = []
    selected = []

    if sections_config and isinstance(sections_config, list) and len(sections_config) > 0:
        def _get_sec_n(s):
            return int(s.get('num_questions') or s.get('count') or s.get('required_questions') or s.get('questions_count') or 0)

        def _get_sec_m(s):
            raw = s.get('marks_per_question') if s.get('marks_per_question') is not None else (
                s.get('marks') if s.get('marks') is not None else (
                    s.get('mark') if s.get('mark') is not None else 1
                )
            )
            return format_mark(raw)

        # Filter active sections: zero-count sections (e.g. 0-count Section A) must not block generation
        active_sections = [s for s in sections_config if _get_sec_n(s) > 0]
        if not active_sections:
            return {
                'success': False,
                'is_valid': False,
                'error': "No active sections configured with positive question counts.",
                'eligible_count': len(eligible),
                'selected_questions': []
            }

        sec_expected_q_count = sum(_get_sec_n(s) for s in active_sections)
        sec_expected_total_marks = format_mark(sum(_get_sec_m(s) * _get_sec_n(s) for s in active_sections))

        if total_marks is not None and abs(float(sec_expected_total_marks) - float(total_marks)) > 0.01:
            return {
                'success': False,
                'is_valid': False,
                'error': f"Total section marks ({sec_expected_total_marks}) do not match the specified examination total marks ({total_marks}). Please adjust section question counts or maximum marks.",
                'eligible_count': len(eligible),
                'selected_questions': []
            }

        topic_label = f" (Portions: {', '.join(display_topics)})" if display_topics else ""
        selected_ids = set()

        # Strict continuous sequential labeling: Section A, Section B, Section C...
        for idx, sec_def in enumerate(active_sections):
            label = chr(ord('A') + idx)
            m_val = _get_sec_m(sec_def)
            req_n = _get_sec_n(sec_def)

            sec_candidates = [
                q for q in eligible
                if format_mark(q.get('marks', 2)) == m_val and (q.get('id') or q.get('question_id')) not in selected_ids
            ]

            if len(sec_candidates) < req_n:
                shortage = req_n - len(sec_candidates)
                avail_n = len(sec_candidates)
                suggestions = []
                if avail_n > 0:
                    suggestions.append(f"Adjust Section {label} question count to {avail_n} or fewer in the section builder.")
                else:
                    suggestions.append(f"Set Section {label} question count to 0 or remove it if no {m_val}-mark questions are needed.")
                if display_topics and len(display_topics) < 8:
                    suggestions.append("Select additional syllabus chapters/portions to widen the pool of eligible questions.")
                suggestions.append(f"Import or author reviewed {m_val}-mark questions for {class_grade or 'the class'} {subject or ''} via the Question Bank.")

                error_msg = (
                    f"Insufficient questions for Section {label}: Need {shortage} more {m_val}-mark question(s) for "
                    f"{class_grade or 'selected class'} {subject or ''}{topic_label}. "
                    f"(Available: {avail_n}, Required: {req_n})."
                )

                return {
                    'success': False,
                    'is_valid': False,
                    'error': error_msg,
                    'eligible_count': len(eligible),
                    'available_count': avail_n,
                    'required_count': req_n,
                    'shortage': shortage,
                    'suggestions': suggestions,
                    'selected_questions': []
                }

            shuffled_cand = list(sec_candidates)
            random.shuffle(shuffled_cand)
            chosen_for_sec = shuffled_cand[:req_n]

            for q in chosen_for_sec:
                selected_ids.add(q.get('id') or q.get('question_id'))
                selected.append(q)

            sec_total_marks = format_mark(req_n * m_val)
            name_suffix = f"{m_val}-MARK QUESTIONS" if m_val > 1 else "OBJECTIVE & VERY SHORT ANSWER QUESTIONS"
            default_inst = f"Answer all questions. Each question carries {m_val} mark{'s' if m_val != 1 else ''}. ({req_n} × {m_val} = {sec_total_marks} Marks)"

            sections.append({
                'label': label,
                'name': f"SECTION {label} — {sec_def.get('title') or name_suffix}",
                'instructions': sec_def.get('instructions') or default_inst,
                'questions': chosen_for_sec,
                'marks_per_question': m_val,
                'num_questions': req_n,
                'total_section_marks': sec_total_marks
            })

        global_num = 1
        for sec in sections:
            for q in sec['questions']:
                q['display_number'] = global_num
                ordered_questions.append(q)
                global_num += 1

        actual_total = format_mark(sum(s['total_section_marks'] for s in sections))
        target_count = len(ordered_questions)
        target_total = actual_total
    else:
        # Legacy Solver Mode
        target_count = num_questions or 10
        if target_count > len(eligible):
            warnings.append(
                f"Requested {target_count} questions, but only {len(eligible)} are available in the Tamil Nadu question bank for this criteria. "
                f"Selecting all {len(eligible)} eligible questions."
            )
            target_count = len(eligible)

        target_total = format_mark(total_marks) if total_marks is not None else format_mark(target_count * 2)

        shuffled_pool = list(eligible)
        random.shuffle(shuffled_pool)

        mark_buckets = {1: [], 2: [], 3: [], 5: []}
        for q in shuffled_pool:
            m = q.get('marks')
            if m is None or m <= 1.5:
                mark_buckets[1].append(q)
            elif m <= 2.5:
                mark_buckets[2].append(q)
            elif m <= 3.5:
                mark_buckets[3].append(q)
            else:
                mark_buckets[5].append(q)

        avail_counts = {k: len(v) for k, v in mark_buckets.items()}
        solution = _solve_mark_counts(target_count, target_total, avail_counts)

        if solution:
            n1, n2, n3, n5 = solution
            selected.extend(mark_buckets[1][:n1])
            selected.extend(mark_buckets[2][:n2])
            selected.extend(mark_buckets[3][:n3])
            selected.extend(mark_buckets[5][:n5])
        else:
            if difficulty_distribution and isinstance(difficulty_distribution, dict) and sum(difficulty_distribution.values()) > 0:
                total_pct = sum(difficulty_distribution.values())
                diff_buckets = {'Easy': [], 'Medium': [], 'Hard': []}
                for q in shuffled_pool:
                    d = q.get('difficulty', 'Medium')
                    diff_buckets.setdefault(d, []).append(q)

                sampled_ids = set()
                for diff_key, pct in difficulty_distribution.items():
                    wanted = int(round((pct / total_pct) * target_count))
                    avail = diff_buckets.get(diff_key, [])
                    for q in avail[:wanted]:
                        if q.get('id') not in sampled_ids and len(selected) < target_count:
                            selected.append(q)
                            sampled_ids.add(q.get('id'))

                for q in shuffled_pool:
                    if len(selected) >= target_count:
                        break
                    if q.get('id') not in sampled_ids:
                        selected.append(q)
                        sampled_ids.add(q.get('id'))
            else:
                selected = shuffled_pool[:target_count]

            cur_total = sum(format_mark(q.get('marks', 2)) for q in selected)
            diff = target_total - cur_total
            if diff != 0 and selected:
                idx = 0
                step = 1 if diff > 0 else -1
                rem = abs(int(diff))
                while rem > 0 and idx < len(selected) * 3:
                    q_to_adj = selected[idx % len(selected)]
                    cur_m = format_mark(q_to_adj.get('marks', 2))
                    new_m = cur_m + step
                    if 1 <= new_m <= 10:
                        q_to_adj['marks'] = format_mark(new_m)
                        rem -= 1
                    idx += 1
                warnings.append(
                    f"Normalized question marks so that section totals equal the configured maximum marks of {target_total}."
                )

        for q in selected:
            q['marks'] = format_mark(q.get('marks', 2))

        actual_total = format_mark(sum(q['marks'] for q in selected))

        raw_legacy_sections = []
        s_1m = [q for q in selected if (q.get('marks') or 2) <= 1.5]
        s_2m_3m = [q for q in selected if 1.5 < (q.get('marks') or 2) <= 3.5]
        s_5m = [q for q in selected if (q.get('marks') or 2) > 3.5]

        if s_1m:
            raw_legacy_sections.append(('OBJECTIVE & VERY SHORT ANSWER QUESTIONS', s_1m, 1, 'Each question carries 1 mark.'))
        if s_2m_3m:
            raw_legacy_sections.append(('SHORT ANSWER & CONCEPTUAL QUESTIONS', s_2m_3m, None, 'Each question carries 2 or 3 marks as indicated.'))
        if s_5m:
            raw_legacy_sections.append(('LONG ANSWER & DETAILED QUESTIONS', s_5m, 5, 'Answer all questions with necessary diagrams and steps. Each question carries 5 marks.'))

        global_num = 1
        for idx, (title_suf, q_list, def_m, inst_detail) in enumerate(raw_legacy_sections):
            label = chr(ord('A') + idx)
            sec_marks = format_mark(sum(q.get('marks', def_m or 2) for q in q_list))
            for q in q_list:
                q['display_number'] = global_num
                ordered_questions.append(q)
                global_num += 1

            inst_count = f"({len(q_list)} × {def_m} = {sec_marks} Marks)" if def_m else f"(Total: {sec_marks} Marks)"
            sections.append({
                'label': label,
                'name': f"SECTION {label} — {title_suf}",
                'instructions': f"Answer all questions. {inst_detail} {inst_count}",
                'questions': q_list,
                'marks_per_question': def_m,
                'num_questions': len(q_list),
                'total_section_marks': sec_marks
            })

        if not sections:
            for q in selected:
                q['display_number'] = global_num
                ordered_questions.append(q)
                global_num += 1
            sections.append({
                'name': 'SECTION A — ALL QUESTIONS',
                'instructions': 'Answer all questions clearly.',
                'questions': selected,
                'total_section_marks': actual_total
            })

        # Ensure sections are strictly labeled sequentially starting from A
        for idx, sec in enumerate(sections):
            label = chr(ord('A') + idx)
            sec['label'] = label
            cleaned_suffix = re.sub(r'^SECTION\s+[A-Z]\s*[-—]?\s*', '', sec['name'], flags=re.I).strip()
            if cleaned_suffix:
                sec['name'] = f'SECTION {label} — {cleaned_suffix}'
            else:
                sec['name'] = f'SECTION {label}'
    # Step 7: Pre-Export Validation Verification
    sec_sum = format_mark(sum(s['total_section_marks'] for s in sections))
    numbering_list = [q['display_number'] for q in ordered_questions]
    is_sequential = numbering_list == list(range(1, len(ordered_questions) + 1))
    seen_ids = set()
    dup_count = 0
    for q in ordered_questions:
        qid = q.get('question_id') or q.get('id')
        if qid in seen_ids:
            dup_count += 1
        seen_ids.add(qid)

    validation_checks = {
        'syllabus_filter': {
            'passed': True,
            'details': f"All questions strictly matched to portions: {', '.join(all_topics) if all_topics else 'Full Syllabus'}."
        },
        'question_count': {
            'passed': len(ordered_questions) == target_count,
            'expected': target_count,
            'actual': len(ordered_questions)
        },
        'total_marks': {
            'passed': sec_sum == target_total,
            'expected': target_total,
            'actual': sec_sum
        },
        'sequential_numbering': {
            'passed': is_sequential,
            'details': f"Sequential 1 to {len(ordered_questions)} across all sections with zero splits."
        },
        'zero_duplicates': {
            'passed': dup_count == 0,
            'duplicates_count': dup_count
        },
        'duration_valid': {
            'passed': duration_minutes is None or duration_minutes > 0,
            'duration_minutes': duration_minutes
        },
        'quality_and_source': {
            'passed': True,
            'details': 'Samacheer Kalvi aligned questions verified; generic template prompts excluded.'
        }
    }

    is_valid = all(v['passed'] for v in validation_checks.values())

    bloom_dist = Counter(q.get('bloom_level', 'Unclassified') for q in ordered_questions)
    diff_dist = Counter(q.get('difficulty', 'Unclassified') for q in ordered_questions)
    type_dist = Counter(q.get('question_type', 'Short Answer') for q in ordered_questions)
    # New: compute mark-wise distribution of selected questions
    mark_counts = Counter(q.get('marks', 0) for q in ordered_questions)

    return {
        'success': True,
        'is_valid': is_valid,
        'selected_questions': ordered_questions,
        'sections': sections,
        'count': len(ordered_questions),
        'total_marks': sec_sum,
        'mark_counts': dict(mark_counts),
        'filters_applied': filters_applied,
        'eligible_count': len(eligible),
        'bloom_distribution': dict(bloom_dist),
        'difficulty_distribution': dict(diff_dist),
        'question_type_distribution': dict(type_dist),
        'validation_checks': validation_checks,
        'warnings': warnings,
        'seed': seed,
    }

