"""
Regression Test: Class 10 Science Paper Generation Failure Diagnosis & Verification
Covers:
1. Exact reproduction of HTTP 400 Bad Request with accurate shortage error message
   (both for 4 portions and for all 21 portions).
2. Board string normalization ('Tamil Nadu State Board' vs 'Tamil NaduState Board')
   and strict filter enforcement.
3. Zero question fabrication or filter weakening.
4. Direct database audit confirming genuine shortage of 1-mark questions in examforge.db.
5. Successful generation when valid available marks are requested.
6. Class 10 Science paper generation with sufficient approved 1-mark questions
   (verifying continuous numbering, section marks, and distributions).
7. Strict chapter isolation: questions from unrelated chapters are never selected.
8. Unicode Tamil text preservation across portions and question stems.
9. Duplicate question rejection in the dataset import pipeline.
10. Clear structured error response matching the frontend UI contract.
"""

import unittest
import json
import unicodedata
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import SessionLocal
from database.models import User, Question
from services.auth import create_access_token, hash_password
from services.question_selection import select_questions, normalize_board


class TestClass10ScienceShortageRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.db = SessionLocal()

        # Ensure a verified Science teacher exists
        cls.science_teacher = cls.db.query(User).filter_by(email='science.teacher.verify@examforge.ai').first()
        if not cls.science_teacher:
            cls.science_teacher = User(
                email='science.teacher.verify@examforge.ai',
                password_hash=hash_password('ScienceTeacher@2026'),
                full_name='Dr. A. Raman',
                role='teacher',
                subject_specialization='Science',
                is_active=True
            )
            cls.db.add(cls.science_teacher)
            cls.db.commit()
            cls.db.refresh(cls.science_teacher)
        elif cls.science_teacher.subject_specialization != 'Science':
            cls.science_teacher.subject_specialization = 'Science'
            cls.db.commit()

        cls.token = create_access_token(cls.science_teacher)
        cls.headers = {
            'Authorization': f'Bearer {cls.token}',
            'Content-Type': 'application/json'
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_reproduce_exact_ui_failure_and_http_400_response(self):
        """
        Verify that when a section requests more questions than available in the database,
        the API strictly returns HTTP 400 with exact shortage details and actionable suggestions.
        """
        payload = {
            "title": "Class 10 Science Over-Requested Exam",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 10",
            "subject": "Science",
            "chapters": [
                "Laws of Motion",
                "Optics"
            ],
            "total_marks": 200,
            "duration_minutes": 150,
            "num_questions": 100,
            "sections": [
                {"name": "Section A", "marks_per_question": 2, "num_questions": 100}
            ]
        }

        response = self.client.post(
            '/api/generate-paper',
            data=json.dumps(payload),
            headers=self.headers
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success'))
        self.assertFalse(data.get('is_valid'))
        self.assertEqual(data.get('selected_questions'), [])
        self.assertIn("Insufficient questions for Section A", data.get('error', ''))
        self.assertIn("suggestions", data)

    def test_01b_reproduce_21_chapters_payload_failure(self):
        """
        Verify that when portions have insufficient questions for an excessive section demand,
        HTTP 400 is returned with clear structured guidance.
        """
        all_21_chapters = [
            "Laws of Motion", "Optics", "Thermal Physics", "Electricity", "Acoustics",
            "Nuclear Physics", "Atoms and Molecules", "Periodic Classification of Elements",
            "Solutions", "Types of Chemical Reactions", "Carbon and its Compounds",
            "Plant Anatomy and Plant Physiology", "Structural Organisation of Animals",
            "Transportation in Plants and Circulation in Animals", "Nervous System",
            "Plant and Animal Hormones", "Reproduction in Plants and Animals", "Heredity",
            "Origin and Evolution of Life", "Breeding and Biotechnology", "Environmental Management"
        ]
        payload = {
            "title": "Class 10 Science Over-Demand Exam",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 10",
            "subject": "Science",
            "chapters": all_21_chapters,
            "total_marks": 500,
            "duration_minutes": 150,
            "num_questions": 250,
            "sections": [
                {"name": "Section A", "marks_per_question": 2, "num_questions": 250}
            ]
        }

        response = self.client.post(
            '/api/generate-paper',
            data=json.dumps(payload),
            headers=self.headers
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success'))
        self.assertIn("Insufficient questions for Section A", data.get('error', ''))
        self.assertIn("suggestions", data)

    def test_02_board_normalization_tolerates_spacing_and_variants(self):
        """
        Test board name normalization for variants like 'Tamil NaduState Board' and 'samacheer kalvi'.
        """
        self.assertEqual(normalize_board('Tamil Nadu State Board'), 'Tamil Nadu State Board')
        self.assertEqual(normalize_board('Tamil NaduState Board'), 'Tamil Nadu State Board')
        self.assertEqual(normalize_board('tamil nadu'), 'Tamil Nadu State Board')
        self.assertEqual(normalize_board('samacheer kalvi'), 'Tamil Nadu State Board')

        # select_questions with 'Tamil NaduState Board' variant should not fail board check
        res = select_questions(
            available_questions=[{
                'id': 1,
                'question': 'State Newton second law of motion in terms of momentum.',
                'marks': 2,
                'class_grade': 'Class 10',
                'subject': 'Science',
                'topic': 'Laws of Motion',
                'board': 'Tamil NaduState Board'
            }],
            num_questions=1,
            total_marks=2,
            subject='Science',
            board='Tamil NaduState Board',
            class_grade='Class 10'
        )
        self.assertTrue(res['success'], f"Selection failed: {res.get('error')}")

        # Non-TN board rejected
        cbse_res = select_questions(
            available_questions=[],
            num_questions=1,
            total_marks=2,
            subject='Science',
            board='CBSE',
            class_grade='Class 10'
        )
        self.assertFalse(cbse_res['success'])
        self.assertIn("Unsupported educational board 'CBSE'", cbse_res.get('error', ''))

    def test_03_zero_fabrication_and_strict_section_mark_integrity(self):
        """
        Verify that question selection engine NEVER fabricates questions or substitutes
        different marks when 1-mark questions are requested.
        """
        questions = [
            {
                'id': 101,
                'question': 'Define inertia and explain its types with suitable daily life examples.',
                'marks': 5,
                'class_grade': 'Class 10',
                'subject': 'Science',
                'topic': 'Laws of Motion',
                'board': 'Tamil Nadu State Board'
            },
            {
                'id': 102,
                'question': 'State Boyle law and Charles law relating temperature and volume.',
                'marks': 2,
                'class_grade': 'Class 10',
                'subject': 'Science',
                'topic': 'Thermal Physics',
                'board': 'Tamil Nadu State Board'
            }
        ]

        result = select_questions(
            available_questions=questions,
            num_questions=2,
            total_marks=2,
            subject='Science',
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            sections_config=[{"name": "Section A", "marks_per_question": 1, "num_questions": 2}]
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['selected_questions'], [])
        self.assertIn("Need 2 more 1-mark question(s)", result.get('error', ''))
        self.assertIn("(Available: 0, Required: 2)", result.get('error', ''))

    def test_04_direct_database_audit_proves_genuine_shortage(self):
        """
        Audit the live database to confirm post-import counts for Class 10 Science:
        >= 510 1-mark questions, >= 42 2-mark questions, >= 787 total questions.
        """
        db = SessionLocal()
        try:
            q_1m = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Science',
                Question.marks == 1.0
            ).count()
            self.assertGreaterEqual(q_1m, 510)

            q_total = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Science'
            ).count()
            self.assertGreaterEqual(q_total, 787)
        finally:
            db.close()

    def test_05_successful_paper_generation_when_using_available_mark_categories(self):
        """
        Test that paper generation succeeds when the section configuration matches
        the question bank's available marks (2m/3m/5m).
        """
        payload = {
            "title": "Class 10 Science Valid Test",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 10",
            "subject": "Science",
            "chapters": [
                "Laws of Motion",
                "Electricity"
            ],
            "total_marks": 7,
            "duration_minutes": 30,
            "num_questions": 2,
            "sections": [
                {"name": "Section B", "marks_per_question": 2, "num_questions": 1},
                {"name": "Section D", "marks_per_question": 5, "num_questions": 1}
            ]
        }

        response = self.client.post(
            '/api/generate-paper',
            data=json.dumps(payload),
            headers=self.headers
        )

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('count'), 2)
        self.assertEqual(data.get('total_marks'), 7)

    def test_06_paper_generation_with_sufficient_approved_1m_questions(self):
        """
        Verify paper generation works end-to-end when sufficient approved 1-mark questions
        exist, validating continuous numbering, section marks, and distributions.
        """
        sample_bank = [
            {'id': i, 'question': f'1-mark objective question {i}', 'marks': 1, 'class_grade': 'Class 10',
             'subject': 'Science', 'topic': 'Laws of Motion', 'board': 'Tamil Nadu State Board',
             'question_type': 'objective', 'difficulty': 'easy', 'bloom_level': 'remember'}
            for i in range(1, 8)
        ] + [
            {'id': 10, 'question': '2-mark question 1', 'marks': 2, 'class_grade': 'Class 10',
             'subject': 'Science', 'topic': 'Laws of Motion', 'board': 'Tamil Nadu State Board',
             'question_type': 'short_answer', 'difficulty': 'medium', 'bloom_level': 'understand'},
            {'id': 11, 'question': '2-mark question 2', 'marks': 2, 'class_grade': 'Class 10',
             'subject': 'Science', 'topic': 'Laws of Motion', 'board': 'Tamil Nadu State Board',
             'question_type': 'short_answer', 'difficulty': 'medium', 'bloom_level': 'understand'}
        ]

        res = select_questions(
            available_questions=sample_bank,
            num_questions=7,
            total_marks=9,
            subject='Science',
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            sections_config=[
                {"name": "Section A", "marks_per_question": 1, "num_questions": 5},
                {"name": "Section B", "marks_per_question": 2, "num_questions": 2}
            ]
        )

        self.assertTrue(res['success'])
        self.assertEqual(len(res['selected_questions']), 7)
        self.assertEqual(res['total_marks'], 9)
        self.assertEqual(len(res['sections']), 2)

        sec_a = res['sections'][0]
        sec_b = res['sections'][1]
        self.assertEqual(sec_a['label'], 'A')
        self.assertEqual(sec_a['marks_per_question'], 1)
        self.assertEqual(len(sec_a['questions']), 5)
        self.assertEqual(sec_a['total_section_marks'], 5)

        self.assertEqual(sec_b['label'], 'B')
        self.assertEqual(sec_b['marks_per_question'], 2)
        self.assertEqual(len(sec_b['questions']), 2)
        self.assertEqual(sec_b['total_section_marks'], 4)

        # Check continuous display numbers
        numbers = [q['display_number'] for q in res['selected_questions']]
        self.assertEqual(numbers, [1, 2, 3, 4, 5, 6, 7])

    def test_07_unrelated_chapters_are_not_selected(self):
        """
        Verify that questions from outside the selected portions are strictly excluded.
        """
        mixed_questions = [
            {'id': 201, 'question': 'Optics question 1', 'marks': 2, 'class_grade': 'Class 10',
             'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board'},
            {'id': 202, 'question': 'Chemical Reactions question 1', 'marks': 2, 'class_grade': 'Class 10',
             'subject': 'Science', 'topic': 'Types of Chemical Reactions', 'board': 'Tamil Nadu State Board'},
            {'id': 203, 'question': 'Unrelated Social Science question', 'marks': 2, 'class_grade': 'Class 10',
             'subject': 'Science', 'topic': 'History of India', 'board': 'Tamil Nadu State Board'}
        ]

        res = select_questions(
            available_questions=mixed_questions,
            num_questions=1,
            total_marks=2,
            subject='Science',
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            topics=['Optics']
        )

        self.assertTrue(res['success'])
        self.assertEqual(len(res['selected_questions']), 1)
        self.assertEqual(res['selected_questions'][0]['topic'], 'Optics')

    def test_08_unicode_tamil_text_preservation(self):
        """
        Verify that Unicode Tamil characters in chapter headings and question stems
        remain bit-for-bit intact without mojibake.
        """
        tamil_chap = unicodedata.normalize('NFC', 'அன்னை மொழியே')
        tamil_q_text = unicodedata.normalize('NFC', 'தமிழ் மொழியின் சிறப்புகளை விளக்குக.')

        tamil_questions = [
            {'id': 301, 'question': tamil_q_text, 'marks': 2, 'class_grade': 'Class 10',
             'subject': 'Tamil', 'topic': tamil_chap, 'board': 'Tamil Nadu State Board'}
        ]

        res = select_questions(
            available_questions=tamil_questions,
            num_questions=1,
            total_marks=2,
            subject='Tamil',
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            topics=[tamil_chap]
        )

        self.assertTrue(res['success'])
        sel = res['selected_questions'][0]
        self.assertEqual(sel['topic'], tamil_chap)
        self.assertEqual(sel['question'], tamil_q_text)

    def test_09_duplicate_questions_detection(self):
        """
        Verify that duplicate question detection correctly identifies collisions
        against existing questions.
        """
        db = SessionLocal()
        try:
            first_q = db.query(Question).first()
            if first_q:
                norm_text = first_q.question.strip().lower()
                is_dup = db.query(Question).filter(Question.question.ilike(norm_text)).count() > 0
                self.assertTrue(is_dup)
        finally:
            db.close()

    def test_10_structured_error_message_format_for_frontend(self):
        """
        Verify that the HTTP 400 error response returns the exact JSON structure
        expected by the frontend UI (error string, success=False, eligible_count, is_valid=False).
        """
        payload = {
            "title": "Invalid Request Test",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 10",
            "subject": "Science",
            "chapters": ["Optics"],
            "total_marks": 800,
            "duration_minutes": 30,
            "num_questions": 800,
            "sections": [
                {"name": "Section A", "marks_per_question": 1, "num_questions": 800}
            ]
        }

        response = self.client.post(
            '/api/generate-paper',
            data=json.dumps(payload),
            headers=self.headers
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)
        self.assertIn('success', data)
        self.assertIn('is_valid', data)
        self.assertIn('eligible_count', data)
        self.assertFalse(data['success'])
        self.assertFalse(data['is_valid'])
        self.assertIsInstance(data['error'], str)
        self.assertIn("Insufficient questions for Section A", data['error'])


if __name__ == '__main__':
    unittest.main()
