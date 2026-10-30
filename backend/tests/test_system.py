"""
Test Suite for ExamForge AI Backend
Verifies preprocessing, models, question selection, database, and PDF generation.
"""

import os
import unittest
import numpy as np

from config import Config
from ml.preprocessing import normalize_text, validate_question_text
from ml.predict import predictor
from services.question_selection import select_questions
from services.pdf_generator import generate_exam_pdf
from database.db import SessionLocal
from database.models import Question, GeneratedPaper


class TestExamForgeSystem(unittest.TestCase):

    def test_text_preprocessing(self):
        """Test text normalization and validation."""
        valid, msg = validate_question_text("What is machine learning?")
        self.assertTrue(valid)
        self.assertEqual(msg, "Valid")

        # Invalid short text
        valid_short, msg_short = validate_question_text("hi?")
        self.assertFalse(valid_short)

        # Empty text
        valid_empty, msg_empty = validate_question_text("")
        self.assertFalse(valid_empty)

        # Normalization
        norm = normalize_text("  What IS the capital of India???  ")
        self.assertEqual(norm, "what is the capital of india???")

    def test_model_loading_and_inference(self):
        """Test inference on both Bloom and Difficulty models."""
        res1 = predictor.classify_question("Define Ohm's law and write its mathematical formula.")
        self.assertIn(res1['bloom']['prediction'], Config.BLOOM_LEVELS)
        self.assertIn(res1['difficulty']['prediction'], Config.DIFFICULTY_LEVELS)
        self.assertGreater(res1['bloom']['confidence'], 0.0)
        self.assertGreater(res1['difficulty']['confidence'], 0.0)

        res2 = predictor.classify_question("Design and evaluate a distributed microservices architecture.")
        self.assertIn(res2['bloom']['prediction'], Config.BLOOM_LEVELS)
        self.assertIn(res2['difficulty']['prediction'], Config.DIFFICULTY_LEVELS)

    def test_question_selection_algorithm(self):
        """Test constraint satisfaction in question selection."""
        dummy_questions = [
            {'id': i, 'question': f'Question {i}', 'subject': 'Physics', 'marks': 5, 'bloom_level': 'Understand', 'difficulty': 'Medium'}
            for i in range(1, 15)
        ]

        # Select 5 questions
        res = select_questions(dummy_questions, num_questions=5, total_marks=25, seed=42)
        self.assertTrue(res['success'])
        self.assertEqual(len(res['selected_questions']), 5)
        self.assertEqual(res['total_marks'], 25)

        # Insufficient questions test
        res_insufficient = select_questions(dummy_questions[:3], num_questions=10)
        self.assertTrue(res_insufficient['success'])
        self.assertEqual(len(res_insufficient['selected_questions']), 3)

    def test_database_queries(self):
        """Verify database holds questions and filters work."""
        db = SessionLocal()
        try:
            count = db.query(Question).count()
            self.assertGreaterEqual(count, 100)

            physics_q = db.query(Question).filter(Question.subject == 'Physics').first()
            self.assertIsNotNone(physics_q)
            self.assertIsNotNone(physics_q.bloom_level)
            self.assertIsNotNone(physics_q.difficulty)
        finally:
            db.close()

    def test_pdf_generation(self):
        """Verify ReportLab PDF generation generates valid file on disk."""
        paper_data = {
            'title': 'Unit Test Assessment Paper',
            'board': 'CBSE',
            'class_grade': 'Class 12',
            'subject': 'Computer Science',
            'total_marks': 10
        }
        questions = [
            {'question': 'What is a stack and what are its core operations?', 'marks': 5, 'bloom_level': 'Remember', 'difficulty': 'Easy'},
            {'question': 'Write an algorithm to invert a binary tree.', 'marks': 5, 'bloom_level': 'Apply', 'difficulty': 'Medium'}
        ]
        filepath, filename = generate_exam_pdf(paper_data, questions)
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(os.path.getsize(filepath) > 1000)

    def test_authentication_and_jwt(self):
        """Test password hashing, JWT creation/decoding, and verification."""
        from services.auth import hash_password, verify_password, create_access_token, decode_access_token
        from database.models import User

        raw_pwd = "SecureTeacherPass@2026"
        hashed = hash_password(raw_pwd)
        self.assertNotEqual(raw_pwd, hashed)
        self.assertTrue(verify_password(raw_pwd, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))

        dummy_user = User(id=99, email="testuser@examforge.ai", role="teacher")
        token = create_access_token(dummy_user)
        self.assertIsInstance(token, str)

        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['sub'], "99")
        self.assertEqual(payload['email'], "testuser@examforge.ai")


if __name__ == '__main__':
    unittest.main()

