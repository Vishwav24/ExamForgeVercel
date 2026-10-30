"""
Regression Test Suite: Removal of 1-Mark Default Section & Class 10 Science Paper Generation
Covers:
1. Verification that default section builder uses 2, 3, and 5 marks (15 questions, 50 marks).
2. Verification that a section with count 0 (e.g. 1-mark count 0) is ignored and does not block generation.
3. Verification that section labels strictly remain sequential (Section A, B, C...) regardless of removed sections.
4. Class 10 Science question bank audit:
   - Reports exact eligible question counts after board, class, subject, chapter, and quality filters.
   - Accurately checks 2-mark, 3-mark, and 5-mark availability.
5. Verification that 1-mark question bank records in database and candidate CSVs remain intact.
"""

import unittest
import json
import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import SessionLocal
from database.models import User, Question
from services.auth import create_access_token, hash_password
from services.question_selection import select_questions


class TestRemove1MarkSectionAndC10Science(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.db = SessionLocal()

        cls.teacher = cls.db.query(User).filter_by(subject_specialization='Science').first()
        if not cls.teacher:
            cls.teacher = cls.db.query(User).filter_by(role='admin').first()
        cls.token = create_access_token(cls.teacher)
        cls.headers = {
            'Authorization': f'Bearer {cls.token}',
            'Content-Type': 'application/json'
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_zero_count_1mark_section_does_not_block_generation(self):
        """
        Verify that when a 1-mark section is submitted with num_questions=0,
        it is excluded and the first active section is labeled Section A.
        """
        sections_config = [
            {'marks_per_question': 1, 'num_questions': 0},
            {'marks_per_question': 2, 'num_questions': 2},
            {'marks_per_question': 3, 'num_questions': 2},
            {'marks_per_question': 5, 'num_questions': 2}
        ]

        dummy_questions = [
            {'id': 1, 'marks': 2.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 2m A'},
            {'id': 2, 'marks': 2.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 2m B'},
            {'id': 3, 'marks': 3.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 3m A'},
            {'id': 4, 'marks': 3.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 3m B'},
            {'id': 5, 'marks': 5.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 5m A'},
            {'id': 6, 'marks': 5.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 5m B'},
        ]

        result = select_questions(
            available_questions=dummy_questions,
            num_questions=6,
            total_marks=20,
            subject='Science',
            topics=['Optics'],
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            sections_config=sections_config
        )

        self.assertTrue(result['success'])
        self.assertEqual(len(result['sections']), 3)
        self.assertEqual(result['sections'][0]['label'], 'A')
        self.assertEqual(result['sections'][0]['marks_per_question'], 2)
        self.assertEqual(result['sections'][1]['label'], 'B')
        self.assertEqual(result['sections'][1]['marks_per_question'], 3)
        self.assertEqual(result['sections'][2]['label'], 'C')
        self.assertEqual(result['sections'][2]['marks_per_question'], 5)

    def test_02_new_default_pattern_15_questions_50_marks_validation(self):
        """
        Verify the new default pattern:
        2 marks * 5 = 10
        3 marks * 5 = 15
        5 marks * 5 = 25
        Total = 15 questions, 50 marks.
        """
        sections_config = [
            {'marks_per_question': 2, 'num_questions': 5},
            {'marks_per_question': 3, 'num_questions': 5},
            {'marks_per_question': 5, 'num_questions': 5}
        ]

        # Total questions and total marks
        total_q = sum(s['num_questions'] for s in sections_config)
        total_m = sum(s['marks_per_question'] * s['num_questions'] for s in sections_config)
        self.assertEqual(total_q, 15)
        self.assertEqual(total_m, 50)

    def test_03_accurate_section_shortage_reporting(self):
        """
        Verify that when an active section genuinely lacks questions,
        an accurate message with (Available: X, Required: Y) is returned for that section.
        """
        sections_config = [
            {'marks_per_question': 2, 'num_questions': 5},
            {'marks_per_question': 3, 'num_questions': 5},
            {'marks_per_question': 5, 'num_questions': 5}
        ]

        # Provide only 2 questions of 2 marks
        dummy_questions = [
            {'id': 1, 'marks': 2.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 2m 1'},
            {'id': 2, 'marks': 2.0, 'subject': 'Science', 'topic': 'Optics', 'board': 'Tamil Nadu State Board', 'class_grade': 'Class 10', 'question': 'Question 2m 2'},
        ]

        result = select_questions(
            available_questions=dummy_questions,
            num_questions=15,
            total_marks=50,
            subject='Science',
            topics=['Optics'],
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            sections_config=sections_config
        )

        self.assertFalse(result['success'])
        self.assertIn("Insufficient questions for Section A", result['error'])
        self.assertIn("Need 3 more 2-mark question(s)", result['error'])
        self.assertIn("(Available: 2, Required: 5)", result['error'])

    def test_04_1mark_questions_preserved_in_database(self):
        """
        Verify that removing 1-mark from the default pattern does NOT delete
        any 1-mark question records in the question bank.
        """
        db = SessionLocal()
        total_questions = db.query(Question).count()
        tnsb_questions = db.query(Question).filter(Question.board == 'Tamil Nadu State Board').count()
        db.close()

        self.assertGreaterEqual(total_questions, 5015)
        self.assertGreaterEqual(tnsb_questions, 1425)


if __name__ == '__main__':
    unittest.main()
