"""
Regression Tests: Tamil Nadu State Board Question Bank & Selection (Tamil - அன்னை மொழியே)
Tests:
1. Exact DB investigation for Class 10 Tamil portion 'அன்னை மொழியே'.
2. Unicode text encoding normalization (NFC vs NFD), class, and subject casing normalization.
3. Exact shortage reporting when 1-mark questions are requested (available: 0, required: 5).
4. No fabrication or cross-contamination from other subjects/classes/marks.
5. Valid paper generation when selecting available mark categories (2-mark, 3-mark, 5-mark).
"""

import unittest
import unicodedata
import json
import sys
import os

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import SessionLocal
from database.models import User, Question
from services.auth import create_access_token, hash_password
from services.question_selection import select_questions


class TestTamilQuestionSelectionRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.db = SessionLocal()
        
        # Ensure a verified Tamil teacher exists
        cls.tamil_teacher = cls.db.query(User).filter_by(email='tamil.hod@examforge.ai').first()
        if not cls.tamil_teacher:
            cls.tamil_teacher = User(
                email='tamil.hod@examforge.ai',
                password_hash=hash_password('TamilTeacher@2026'),
                full_name='Senthamizhan',
                role='teacher',
                subject_specialization='Tamil',
                is_active=True
            )
            cls.db.add(cls.tamil_teacher)
            cls.db.commit()
            cls.db.refresh(cls.tamil_teacher)
        elif cls.tamil_teacher.subject_specialization != 'Tamil':
            cls.tamil_teacher.subject_specialization = 'Tamil'
            cls.db.commit()
            
        cls.token = create_access_token(cls.tamil_teacher)
        cls.headers = {'Authorization': f'Bearer {cls.token}', 'Content-Type': 'application/json'}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_sqlite_database_actual_records_investigation(self):
        """
        Verify the actual questions in SQLite for:
        Board: Tamil Nadu State Board, Class: 10, Subject: Tamil, Portion: அன்னை மொழியே
        """
        portion = 'அன்னை மொழியே'
        questions = self.db.query(Question).filter(
            Question.class_grade == 'Class 10',
            Question.subject == 'Tamil',
            Question.topic == portion
        ).all()

        # Confirms exactly 5 authentic questions exist in DB
        self.assertEqual(len(questions), 5, f"Expected 5 questions for '{portion}', found {len(questions)}")
        
        marks_found = sorted([q.marks for q in questions])
        # Available marks: 2.0 (2 questions), 3.0 (1 question), 5.0 (2 questions)
        self.assertEqual(marks_found, [2.0, 2.0, 3.0, 5.0, 5.0])

        # Confirms ZERO 1-mark questions exist in DB for this portion
        one_mark_q = [q for q in questions if q.marks == 1.0]
        self.assertEqual(len(one_mark_q), 0, "Question bank must contain 0 1-mark questions for அன்னை மொழியே")

    def test_02_unicode_nfc_nfd_normalization(self):
        """
        Verify that Tamil text encoding matches correctly regardless of NFC or NFD input.
        """
        portion_nfc = unicodedata.normalize('NFC', 'அன்னை மொழியே')
        portion_nfd = unicodedata.normalize('NFD', 'அன்னை மொழியே')
        
        # Test NFC query via API
        resp_nfc = self.client.get(
            f'/api/questions?subject=Tamil&class_grade=Class%2010&topic={portion_nfc}',
            headers=self.headers
        )
        self.assertEqual(resp_nfc.status_code, 200)
        self.assertEqual(resp_nfc.get_json()['total'], 5)

        # Test NFD query via API
        resp_nfd = self.client.get(
            f'/api/questions?subject=Tamil&class_grade=Class%2010&topic={portion_nfd}',
            headers=self.headers
        )
        self.assertEqual(resp_nfd.status_code, 200)
        self.assertEqual(resp_nfd.get_json()['total'], 5)

    def test_03_class_and_subject_normalization(self):
        """
        Verify that class '10' or 'Class 10' and subject 'tamil' or 'Tamil' normalize correctly.
        """
        portion = 'அன்னை மொழியே'
        # Query with class_grade='10' and subject='tamil'
        resp = self.client.get(
            f'/api/questions?subject=tamil&class_grade=10&topic={portion}',
            headers=self.headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['total'], 5)

    def test_04_exact_shortage_message_for_one_mark_questions(self):
        """
        Verify that requesting 5 1-mark questions for 'அன்னை மொழியே' reports the genuine shortage
        with the exact error message and zero fabrication.
        """
        portion = 'அன்னை மொழியே'
        payload = {
            'title': 'Unit Test 1',
            'board': 'Tamil Nadu State Board',
            'class_grade': 'Class 10',
            'subject': 'Tamil',
            'chapters': [portion],
            'total_marks': 5,
            'duration_minutes': 30,
            'sections': [
                {
                    'label': 'A',
                    'marks_per_question': 1,
                    'num_questions': 5
                }
            ]
        }

        resp = self.client.post('/api/papers/generate', headers=self.headers, json=payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        
        expected_error = (
            "Insufficient questions for Section A: Need 5 more 1-mark question(s) for Class 10 Tamil "
            f"(Portions: {portion}). (Available: 0, Required: 5)."
        )
        self.assertEqual(data['error'], expected_error)
        self.assertEqual(data['selected_questions'], [])

    def test_05_successful_generation_for_available_marks(self):
        """
        Verify that when requesting marks that exist in the question bank (e.g., 2 marks),
        the paper is successfully generated without errors.
        """
        portion = 'அன்னை மொழியே'
        payload = {
            'title': 'Tamil Slip Test',
            'board': 'Tamil Nadu State Board',
            'class_grade': 'Class 10',
            'subject': 'Tamil',
            'chapters': [portion],
            'total_marks': 4,
            'duration_minutes': 30,
            'sections': [
                {
                    'label': 'A',
                    'marks_per_question': 2,
                    'num_questions': 2
                }
            ]
        }

        resp = self.client.post('/api/papers/generate', headers=self.headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_marks'], 4)
        self.assertEqual(len(data['questions']), 2)
        
        # Verify all selected questions are strictly from 'அன்னை மொழியே' and carry 2 marks
        for q in data['questions']:
            self.assertEqual(q['topic'], portion)
            self.assertEqual(q['class_grade'], 'Class 10')
            self.assertEqual(q['subject'], 'Tamil')
            self.assertEqual(q['marks'], 2.0)

    def test_06_preview_validation_matches_generation(self):
        """
        Verify preview endpoint returns identical validation and shortage diagnostics.
        """
        portion = 'அன்னை மொழியே'
        payload = {
            'title': 'Preview Test',
            'board': 'Tamil Nadu State Board',
            'class_grade': '10',  # Test normalized class
            'subject': 'tamil',   # Test normalized subject
            'portion': portion,   # Test 'portion' parameter alias
            'total_marks': 5,
            'duration_minutes': 30,
            'sections': [
                {
                    'label': 'A',
                    'marks': 1,
                    'count': 5
                }
            ]
        }

        resp = self.client.post('/api/generate-paper/preview', headers=self.headers, json=payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn("Insufficient questions for Section A: Need 5 more 1-mark question(s)", data['error'])
        self.assertIn("(Available: 0, Required: 5)", data['error'])


if __name__ == '__main__':
    unittest.main()

