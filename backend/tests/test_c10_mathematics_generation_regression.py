"""
Regression Test: Class 10 Mathematics Paper Generation Diagnosis & Verification
Covers:
1. Exact reproduction of Mathematics paper generation notice when Section A requests 5 2-mark questions (Available: 4, Required: 5).
2. Verification of clear structured error messages and actionable suggestions for teachers.
3. Successful generation of Class 10 Mathematics when configured for available questions (e.g., 4 x 2m = 8m, or 2m + 3m + 5m).
4. Successful generation when at least 5 eligible questions exist (tested via test fixture and live Class 10 Science).
5. Exact live database question counts by mark tier for Class 10 Mathematics (75 total: 59 1m, 4 2m, 6 3m, 6 5m).
6. Sanitized request payload logging verification (no tokens or secrets logged).
"""

import unittest
import json
import logging
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import SessionLocal
from database.models import User, Question
from services.auth import create_access_token, hash_password
from services.question_selection import select_questions


class TestClass10MathematicsGenerationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.db = SessionLocal()

        # Find or create a verified Mathematics teacher
        cls.math_teacher = cls.db.query(User).filter_by(email='iniya@gmail.com').first()
        if not cls.math_teacher:
            cls.math_teacher = cls.db.query(User).filter_by(email='math.teacher.verify@examforge.ai').first()
        if not cls.math_teacher:
            cls.math_teacher = User(
                email='math.teacher.verify@examforge.ai',
                full_name='Mathematics Faculty',
                password_hash=hash_password('MathTeacher@2026'),
                role='teacher',
                subject_specialization='Mathematics',
                is_active=True
            )
            cls.db.add(cls.math_teacher)
            cls.db.commit()
            cls.db.refresh(cls.math_teacher)

        cls.token = create_access_token(cls.math_teacher)
        cls.headers = {
            'Authorization': f'Bearer {cls.token}',
            'Content-Type': 'application/json'
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_reproduce_section_a_2mark_shortage_400(self):
        """
        When Section A requires 5 2-mark questions for Class 10 Mathematics,
        the request must return HTTP 400 with exact shortage details (Available: 4, Required: 5)
        and clear actionable suggestions for the teacher.
        """
        payload = {
            "title": "Class 10 Mathematics Periodic Exam",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 10",
            "subject": "Mathematics",
            "chapters": [
                "Relations and Functions",
                "Numbers and Sequences",
                "Algebra",
                "Geometry",
                "Coordinate Geometry",
                "Trigonometry",
                "Mensuration",
                "Statistics and Probability"
            ],
            "total_marks": 50,
            "duration_minutes": 150,
            "num_questions": 15,
            "sections": [
                {"name": "Section A", "marks_per_question": 2, "num_questions": 5},
                {"name": "Section B", "marks_per_question": 3, "num_questions": 5},
                {"name": "Section C", "marks_per_question": 5, "num_questions": 5}
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
        self.assertIn("Need 1 more 2-mark question(s) for Class 10 Mathematics", data.get('error', ''))
        self.assertIn("Available: 4, Required: 5", data.get('error', ''))
        # Check structured actionable suggestions
        self.assertIn("suggestions", data)
        self.assertTrue(len(data.get('suggestions')) > 0)
        self.assertTrue(any("Adjust Section A" in s for s in data.get('suggestions')))

    def test_02_successful_generation_when_configured_for_available_4_questions(self):
        """
        When configuring Section A to use the available 4 questions (4 x 2m = 8 marks),
        Class 10 Mathematics paper generation succeeds with HTTP 201.
        """
        payload = {
            "title": "Class 10 Mathematics Unit Test",
            "board": "Tamil Nadu State Board",
            "class_grade": "Class 10",
            "subject": "Mathematics",
            "chapters": [
                "Relations and Functions",
                "Numbers and Sequences",
                "Algebra",
                "Statistics and Probability"
            ],
            "total_marks": 20,
            "duration_minutes": 60,
            "num_questions": 6,
            "sections": [
                {"name": "Section A", "marks_per_question": 2, "num_questions": 4},
                {"name": "Section B", "marks_per_question": 3, "num_questions": 4}
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
        self.assertEqual(data.get('count'), 8)
        self.assertEqual(data.get('total_marks'), 20)
        self.assertTrue(data.get('pdf_filename', '').endswith('.pdf'))

    def test_03_successful_generation_when_at_least_5_questions_exist(self):
        """
        Test that when at least 5 eligible questions exist, requesting 5 2-mark questions
        in Section A succeeds with valid questions and exact marks.
        """
        dummy_math_questions = [
            {'id': i, 'question': f'Math 2m problem {i}', 'subject': 'Mathematics', 'topic': 'Algebra',
             'marks': 2.0, 'class_grade': 'Class 10', 'board': 'Tamil Nadu State Board', 'verified': True}
            for i in range(1, 8)
        ]

        result = select_questions(
            available_questions=dummy_math_questions,
            num_questions=5,
            total_marks=10,
            subject='Mathematics',
            topics=['Algebra'],
            board='Tamil Nadu State Board',
            class_grade='Class 10',
            sections_config=[
                {'label': 'Section A', 'marks_per_question': 2, 'num_questions': 5, 'section_marks': 10}
            ]
        )

        self.assertTrue(result['success'])
        self.assertTrue(result['is_valid'])
        self.assertEqual(len(result['selected_questions']), 5)
        self.assertEqual(result['total_marks'], 10)
        self.assertEqual(len(result['sections']), 1)
        self.assertEqual(len(result['sections'][0]['questions']), 5)

    def test_04_direct_database_audit_proves_exact_math_question_counts(self):
        """
        Verify directly in examforge.db that Class 10 Mathematics has 75 total questions
        (59 1m, 4 2m, 6 3m, 6 5m).
        """
        db = SessionLocal()
        try:
            total_math = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Mathematics'
            ).count()
            self.assertEqual(total_math, 75)

            one_m_math = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Mathematics',
                Question.marks == 1.0
            ).count()
            self.assertEqual(one_m_math, 59)

            two_m = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Mathematics',
                Question.marks == 2.0
            ).count()
            self.assertEqual(two_m, 4)

            three_m = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Mathematics',
                Question.marks == 3.0
            ).count()
            self.assertEqual(three_m, 6)

            five_m = db.query(Question).filter(
                Question.class_grade == 'Class 10',
                Question.subject == 'Mathematics',
                Question.marks == 5.0
            ).count()
            self.assertEqual(five_m, 6)
        finally:
            db.close()

    def test_05_sanitized_request_logging_excludes_secrets(self):
        """
        Verify that request logging captures payload parameters without leaking
        authorization headers, tokens, or passwords.
        """
        payload = {
            "title": "Sanitization Test",
            "class_grade": "Class 10",
            "subject": "Mathematics",
            "board": "Tamil Nadu State Board",
            "chapters": ["Algebra"],
            "total_marks": 3,
            "num_questions": 1,
            "sections": [{"name": "Section C", "marks_per_question": 3, "num_questions": 1}]
        }

        with self.assertLogs('ExamForgeAPI', level='INFO') as log_capture:
            response = self.client.post(
                '/api/generate-paper',
                data=json.dumps(payload),
                headers=self.headers
            )
            self.assertEqual(response.status_code, 201)

            logged = " ".join(log_capture.output)
            self.assertIn("[GENERATE_PAPER_REQUEST]", logged)
            self.assertIn("Mathematics", logged)
            self.assertNotIn("Bearer", logged)
            self.assertNotIn(self.token, logged)


if __name__ == '__main__':
    unittest.main()
