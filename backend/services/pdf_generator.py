"""
PDF Generation Service using ReportLab for Tamil Nadu State Board (Classes 6–12)
Produces formal, printable examination papers and teacher summaries.
"""

import os
import sys
import re
import html
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config

NAVY = HexColor('#1e3a5f')
DARK_BLUE = HexColor('#2c5282')
LIGHT_BG = HexColor('#f7fafc')
BORDER_GRAY = HexColor('#cbd5e0')
ACCENT = HexColor('#2b6cb0')


def format_marks(val):
    """Format marks as integer if whole, or float if fractional (eliminates '40.0')."""
    if val is None:
        return "0"
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else f"{f:.1f}"
    except (ValueError, TypeError):
        return str(val)


def create_styles():
    """Create custom paragraph styles for formal state board examination papers."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='BoardHeader',
        parent=styles['Normal'],
        fontSize=11,
        textColor=DARK_BLUE,
        spaceAfter=2,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        name='ExamTitle',
        parent=styles['Title'],
        fontSize=15,
        leading=18,
        textColor=NAVY,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        name='ExamSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DARK_BLUE,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        name='MetaKey',
        parent=styles['Normal'],
        fontSize=9.5,
        textColor=NAVY,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    ))

    styles.add(ParagraphStyle(
        name='MetaVal',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=HexColor('#2d3748'),
        fontName='Helvetica',
        alignment=TA_LEFT
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=10.5,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=3,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        name='SectionInstruction',
        parent=styles['Normal'],
        fontSize=8.5,
        textColor=HexColor('#4a5568'),
        spaceBefore=1,
        spaceAfter=4,
        fontName='Helvetica-Oblique',
    ))

    styles.add(ParagraphStyle(
        name='QuestionText',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13.5,
        spaceBefore=3,
        spaceAfter=2,
        fontName='Helvetica',
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        name='MarksText',
        parent=styles['Normal'],
        fontSize=9.5,
        textColor=DARK_BLUE,
        alignment=TA_RIGHT,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        name='InstructionText',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=12,
        spaceBefore=1,
        spaceAfter=1,
        fontName='Helvetica',
        leftIndent=10,
    ))

    styles.add(ParagraphStyle(
        name='FooterText',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#718096'),
        alignment=TA_CENTER,
        fontName='Helvetica',
    ))

    return styles


def generate_exam_pdf(
    paper_data,
    questions,
    output_dir=None,
    sections=None,
    include_teacher_labels=False
):
    """
    Generate a formatted Tamil Nadu State Board examination paper PDF.
    Features:
    - Candidate Register Number input boxes
    - Guaranteed one-line duration formatting
    - Strict integer mark formatting (no '40.0')
    - Sequential question numbering across all sections
    - Clean margins and consistent alignment
    """
    if output_dir is None:
        output_dir = Config.GENERATED_PAPERS_DIR
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_title = "".join(c for c in paper_data.get('title', 'exam') if c.isalnum() or c in ' _-')[:40]
    filename = f"tnsb_{safe_title.replace(' ', '_')}_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )

    styles = create_styles()
    story = []

    # --- Header ---
    board_name = paper_data.get('board') or 'Tamil Nadu State Board'
    if 'tamil nadu' in board_name.lower() or 'samacheer' in board_name.lower():
        story.append(Paragraph("TAMIL NADU STATE BOARD — SAMACHEER KALVI", styles['BoardHeader']))
    else:
        story.append(Paragraph(board_name.upper(), styles['BoardHeader']))

    exam_title = paper_data.get('title', 'Terminal Examination')
    story.append(Paragraph(exam_title.upper(), styles['ExamTitle']))

    # --- Metadata & Candidate Register Number Box ---
    class_val = paper_data.get('class_grade', 'Class 10')
    subject_val = paper_data.get('subject', 'Science')
    duration_min = paper_data.get('duration_minutes', 90)

    # Format duration with non-breaking space so it NEVER wraps across lines
    if duration_min >= 60:
        h = duration_min // 60
        m = duration_min % 60
        dur_str = f"{h}h&nbsp;{m}m" if m > 0 else f"{h}h"
    else:
        dur_str = f"{duration_min}&nbsp;Mins"

    max_marks_raw = paper_data.get('total_marks', sum(q.get('marks', 0) for q in questions))
    max_marks_str = format_marks(max_marks_raw)

    # 8-digit register number boxes
    reg_boxes = Table([[''] * 8], colWidths=[0.52 * cm] * 8, rowHeights=[0.55 * cm])
    reg_boxes.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.75, NAVY),
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#ffffff')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    reg_subtable = Table([
        [Paragraph("<b>Register Number:</b>", styles['MetaKey']), reg_boxes]
    ], colWidths=[3.2 * cm, 5.0 * cm])
    reg_subtable.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # Total width = 4.2 + 4.8 + 4.6 + 4.4 = 18.0 cm (printable width of A4 with 1.5cm margins)
    meta_table_data = [
        [
            Paragraph(f"<b>Class:</b> {class_val}", styles['MetaVal']),
            Paragraph(f"<b>Subject:</b> {subject_val}", styles['MetaVal']),
            Paragraph(f"<b>Time Allowed:</b> {dur_str}", styles['MetaVal']),
            Paragraph(f"<b>Maximum Marks:</b> {max_marks_str}", styles['MetaVal']),
        ],
        [
            Paragraph("<b>Candidate Name:</b> ___________________________", styles['MetaVal']),
            Paragraph("", styles['MetaVal']),  # Span placeholder
            reg_subtable,
            Paragraph("", styles['MetaVal']),  # Span placeholder
        ]
    ]

    meta_table = Table(meta_table_data, colWidths=[4.2 * cm, 4.8 * cm, 4.6 * cm, 4.4 * cm])
    meta_table.setStyle(TableStyle([
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (2, 1), (3, 1)),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_GRAY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(Spacer(1, 4))
    story.append(meta_table)
    story.append(Spacer(1, 5))

    # --- General Instructions ---
    story.append(HRFlowable(width="100%", color=NAVY, thickness=1.2))
    story.append(Spacer(1, 3))
    story.append(Paragraph("<b>GENERAL INSTRUCTIONS:</b>", styles['MetaKey']))

    instructions = [
        "Check that the question paper contains all pages and all questions are printed legibly.",
        "Candidate must enter their Register Number in the boxes provided above and on the answer booklet.",
        "Marks for each question or section are indicated against the respective items.",
        "Rough work should be carried out only in the designated margins or rough sheets provided."
    ]
    if paper_data.get('topic'):
        instructions.append(f"Portions covered: {paper_data['topic']}")

    for inst in instructions:
        story.append(Paragraph(f"• {inst}", styles['InstructionText']))

    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", color=BORDER_GRAY, thickness=1))

    # --- Questions and Sections ---
    if not sections:
        s_a = [q for q in questions if (q.get('marks') or 2) <= 1.5]
        s_b = [q for q in questions if 1.5 < (q.get('marks') or 2) <= 3.5]
        s_c = [q for q in questions if (q.get('marks') or 2) > 3.5]

        raw_sections = []
        if s_a:
            raw_sections.append((s_a, '(Objective & Very Short Answer)', 1, 'Each question carries 1 mark.'))
        if s_b:
            raw_sections.append((s_b, '(Short Answer & Conceptual)', 2, 'Each question carries 2 or 3 marks as indicated.'))
        if s_c:
            raw_sections.append((s_c, '(Long Answer & Descriptive)', 5, 'Answer all questions in detail with necessary diagrams/working. Each carries 5 marks.'))
        if not raw_sections:
            raw_sections.append((questions, '', 2, 'Answer all questions.'))

        sections = []
        for idx, (q_list, title_suf, m_val, inst) in enumerate(raw_sections):
            label = chr(ord('A') + idx)
            sec_m = format_marks(sum(q.get('marks', m_val) for q in q_list))
            sec_name = f'SECTION {label} — {title_suf}'.strip() if title_suf else f'SECTION {label}'
            sections.append({
                'label': label,
                'name': sec_name,
                'instructions': f'Answer all questions. {inst} ({len(q_list)} × {m_val} = {sec_m} Marks)' if m_val else f'Answer all questions. (Total: {sec_m} Marks)',
                'questions': q_list,
                'total_section_marks': sec_m
            })
    else:
        # Strictly normalize section labels to Section A, B, C... in displayed order
        normalized_sections = []
        for idx, sec in enumerate(sections):
            label = chr(ord('A') + idx)
            sec_copy = dict(sec)
            sec_copy['label'] = label
            old_name = sec_copy.get('name', 'SECTION')
            cleaned_suffix = re.sub(r'^SECTION\s+[A-Z]\s*[-—]?\s*', '', old_name, flags=re.I).strip()
            if cleaned_suffix:
                sec_copy['name'] = f'SECTION {label} — {cleaned_suffix}'
            else:
                sec_copy['name'] = f'SECTION {label}'
            normalized_sections.append(sec_copy)
        sections = normalized_sections

    # Continuous sequential numbering across sections
    q_global_num = 1
    for sec in sections:
        sec_title = sec.get('name', 'SECTION')
        story.append(Spacer(1, 6))
        story.append(Paragraph(sec_title, styles['SectionHeader']))
        if sec.get('instructions'):
            story.append(Paragraph(sec['instructions'], styles['SectionInstruction']))

        for q in sec.get('questions', []):
            marks_val = q.get('marks', 2.0)
            marks_str = f"[{format_marks(marks_val)}]"

            q_text = q.get('question', '').strip()
            num = q.get('display_number') or q_global_num
            q_global_num = max(q_global_num + 1, num + 1)
            safe_q_text = html.escape(q_text)

            # Format question row as 2-column table: Question on left, Marks on right
            row_data = [
                [
                    Paragraph(f"<b>{num}.</b>  {safe_q_text}", styles['QuestionText']),
                    Paragraph(marks_str, styles['MarksText'])
                ]
            ]
            q_table = Table(row_data, colWidths=[16.3 * cm, 1.7 * cm])
            q_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(q_table)

            if include_teacher_labels:
                lbls = []
                if q.get('bloom_level'):
                    lbls.append(f"Bloom: {q['bloom_level']}")
                if q.get('difficulty'):
                    lbls.append(f"Difficulty: {q['difficulty']}")
                if q.get('topic'):
                    lbls.append(f"Chapter: {q['topic']}")
                if lbls:
                    story.append(Paragraph(f"<font color='#718096' size='8'><i>({', '.join(lbls)})</i></font>", styles['InstructionText']))

    # --- Footer ---
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", color=NAVY, thickness=1.2))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        f"TAMIL NADU STATE BOARD CURRICULUM — TOTAL QUESTIONS: {len(questions)} | MAXIMUM MARKS: {max_marks_str}",
        styles['FooterText']
    ))
    story.append(Paragraph("ExamForge AI Evaluation & Examination Management System", styles['FooterText']))

    doc.build(story)
    return filepath, filename


def generate_teacher_summary_pdf(paper_data, questions, output_dir=None):
    """Generate summary PDF for teachers."""
    return generate_exam_pdf(paper_data, questions, output_dir=output_dir, include_teacher_labels=True)

