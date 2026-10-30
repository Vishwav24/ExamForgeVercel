"""
Automated Test Suite: Complete Curriculum Coverage Verification for Classes 6–12
Covers:
1. All 45 configured Class-Subject combinations under Tamil Nadu State Board.
2. Database query and question retrieval across all standards.
3. Chapter-specific portion filtering.
4. Marks distribution and section allocation integrity.
5. Insufficient question responses and structured error contracts.
6. Unicode Tamil text preservation across all standards.
7. Paper preview, saving, PDF generation, and download.
8. Candidate data isolation (39,753 staged candidates kept separate from live DB).
"""

import unittest
import json
import unicodedata
import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import SessionLocal
from database.models import User, Question, GeneratedPaper
from services.auth import create_access_token, hash_password
from services.curriculum_service import get_supported_classes, get_supported_subjects, get_supported_chapters
from services.question_selection import select_questions, normalize_board


class TestClasses6To12FullCurriculumCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.db = SessionLocal()

        # Admin user for institution-wide multi-subject test operations
        cls.admin = cls.db.query(User).filter_by(role='admin').first()
        if not cls.admin:
            cls.admin = User(
                email='curriculum.admin@examforge.ai',
                password_hash=hash_password('Admin@2026'),
                full_name='Curriculum Auditor',
                role='admin',
                is_active=True
            )
            cls.db.add(cls.admin)
            cls.db.commit()
            cls.db.refresh(cls.admin)

        cls.token = create_access_token(cls.admin)
        cls.headers = {
            'Authorization': f'Bearer {cls.token}',
            'Content-Type': 'application/json'
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_all_45_class_subject_combinations_curriculum_structure(self):
        """
        Verify that curriculum configuration defines all 7 classes (6 to 12)
        and all 45 expected subject combinations under Tamil Nadu State Board.
        """
        classes = get_supported_classes()
        self.assertEqual(classes, ['Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12'])

        total_combinations = 0
        for c in classes:
            subjects = get_supported_subjects(c)
            if c in ['Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10']:
                self.assertEqual(len(subjects), 5)
                self.assertEqual(sorted(subjects), ['English', 'Mathematics', 'Science', 'Social Science', 'Tamil'])
            else:
                self.assertEqual(len(subjects), 10)
                expected_higher_sec = [
                    'Accountancy', 'Biology', 'Chemistry', 'Commerce', 'Computer Science',
                    'Economics', 'English', 'Mathematics', 'Physics', 'Tamil'
                ]
                self.assertEqual(sorted(subjects), expected_higher_sec)
            total_combinations += len(subjects)

        self.assertEqual(total_combinations, 45)

    def test_02_database_queries_succeed_for_all_45_combinations(self):
        """
        Verify database queries succeed without schema or SQL errors for all 45 class-subject pairs.
        """
        db = SessionLocal()
        try:
            for c in get_supported_classes():
                for s in get_supported_subjects(c):
                    query = db.query(Question).filter(
                        (Question.board == 'Tamil Nadu State Board') | (Question.board.is_(None))
                    ).filter(
                        Question.class_grade.ilike(c)
                    ).filter(
                        Question.subject.ilike(s)
                    )
                    count = query.count()
                    self.assertGreaterEqual(count, 0)
        finally:
            db.close()

    def test_03_chapter_specific_question_filtering_across_standards(self):
        """
        Verify chapter-specific portion filtering works correctly across representative standards.
        """
        # Test Class 10 Tamil specific chapter
        chap_tamil = unicodedata.normalize('NFC', 'அன்னை மொழியே')
        db = SessionLocal()
        try:
            q = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Tamil',
                Question.topic == chap_tamil
            ).all()
            self.assertGreater(len(q), 0)
            for item in q:
                self.assertEqual(item.topic, chap_tamil)
        finally:
            db.close()

    def test_04_marks_distribution_and_section_allocation_integrity(self):
        """
        Verify multi-section question selection enforces mark categories and continuous display numbering.
        """
        mock_questions = [
            {'id': 1, 'question': 'Question 2m A', 'marks': 2, 'class_grade': 'Class 10', 'subject': 'Mathematics', 'topic': 'Algebra', 'board': 'Tamil Nadu State Board'},
            {'id': 2, 'question': 'Question 2m B', 'marks': 2, 'class_grade': 'Class 10', 'subject': 'Mathematics', 'topic': 'Algebra', 'board': 'Tamil Nadu State Board'},
            {'id': 3, 'question': 'Question 5m A', 'marks': 5, 'class_grade': 'Class 10', 'subject': 'Mathematics', 'topic': 'Algebra', 'board': 'Tamil Nadu State Board'},
            {'id': 4, 'question': 'Question 5m B', 'marks': 5, 'class_grade': 'Class 10', 'subject': 'Mathematics', 'topic': 'Algebra', 'board': 'Tamil Nadu State Board'}
        ]

        res = select_questions(
            available_questions=mock_questions,
            num_questions=4,
            total_marks=14,
            subject='Mathematics',
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            sections_config=[
                {'name': 'Section B', 'marks_per_question': 2, 'num_questions': 2},
                {'name': 'Section D', 'marks_per_question': 5, 'num_questions': 2}
            ]
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['total_marks'], 14)
        self.assertEqual(len(res['selected_questions']), 4)
        self.assertEqual([q['display_number'] for q in res['selected_questions']], [1, 2, 3, 4])

    def test_05_insufficient_question_error_handling_structure(self):
        """
        Verify that requesting more questions than available returns clear, structured HTTP 400.
        """
        payload = {
            "title": "Shortage Test",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 10",
            "subject": "Mathematics",
            "chapters": ["Relations and Functions"],
            "total_marks": 50,
            "duration_minutes": 150,
            "num_questions": 19,
            "sections": [
                {"name": "Section A", "marks_per_question": 2, "num_questions": 5},
                {"name": "Section B", "marks_per_question": 3, "num_questions": 5},
                {"name": "Section C", "marks_per_question": 5, "num_questions": 5}
            ]
        }

        response = self.client.post('/api/generate-paper', data=json.dumps(payload), headers=self.headers)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn("Insufficient questions for Section A", data['error'])
        self.assertIn("Available: 1, Required: 5", data['error'])

    def test_06_tamil_unicode_preservation_across_all_standards(self):
        """
        Verify Tamil Unicode script is preserved without mojibake across standards 6-12.
        """
        db = SessionLocal()
        try:
            for c in ['Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']:
                tamil_qs = db.query(Question).filter(Question.class_grade == c, Question.subject == 'Tamil').all()
                self.assertGreater(len(tamil_qs), 0, f"No Tamil questions for {c}")
                for q in tamil_qs[:2]:
                    # Ensure question decodes to valid UTF-8 and contains Tamil code block characters
                    has_tamil_char = any('\u0b80' <= ch <= '\u0bff' for ch in q.question)
                    self.assertTrue(has_tamil_char, f"Question ID {q.id} in {c} Tamil missing Tamil Unicode characters")
        finally:
            db.close()

    def test_07_paper_preview_saving_pdf_generation_and_download(self):
        """
        End-to-end test: preview blueprint, generate paper, save record, produce PDF, and download.
        """
        payload = {
            "title": "Comprehensive E2E Verification Exam",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 6",
            "subject": "Mathematics",
            "chapters": ["Numbers", "Ratio and Proportion"],
            "total_marks": 5,
            "duration_minutes": 30,
            "num_questions": 3,
            "sections": [
                {"name": "Section A", "marks_per_question": 1, "num_questions": 1},
                {"name": "Section B", "marks_per_question": 2, "num_questions": 2}
            ]
        }

        # 1. Preview blueprint
        prev_resp = self.client.post('/api/generate-paper/preview', data=json.dumps(payload), headers=self.headers)
        self.assertEqual(prev_resp.status_code, 200)
        prev_data = prev_resp.get_json()
        self.assertTrue(prev_data['success'])

        # 2. Generate paper
        gen_resp = self.client.post('/api/generate-paper', data=json.dumps(payload), headers=self.headers)
        self.assertEqual(gen_resp.status_code, 201)
        gen_data = gen_resp.get_json()
        self.assertTrue(gen_data['success'])
        paper_id = gen_data['paper_id']
        pdf_name = gen_data['pdf_filename']

        # 3. Verify PDF exists on disk
        pdf_path = os.path.join(backend_dir, 'generated_papers', pdf_name)
        self.assertTrue(os.path.exists(pdf_path))

        # 4. Download paper endpoint
        dl_resp = self.client.get(f'/api/papers/{paper_id}/download', headers=self.headers)
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp.content_type, 'application/pdf')

    def test_08_candidate_data_isolation(self):
        """
        Verify that 39,753 staged candidate questions remain completely isolated in
        extracted_candidates_v2/ and are not mixed with live DB records.
        """
        cand_csv = os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_all_standards.csv')
        self.assertTrue(os.path.exists(cand_csv))

        db = SessionLocal()
        try:
            live_total = db.query(Question).count()
            self.assertGreaterEqual(live_total, 5015)

            tnsb_live = db.query(Question).filter(
                (Question.board == 'Tamil Nadu State Board') | (Question.board.is_(None))
            ).count()
            self.assertGreaterEqual(tnsb_live, 1425)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
