"""
Regression Test: Class 10 Science English-Medium Paper Generation & Quality Assurance
Verifies:
1. Generation of 50-mark Class 10 Science paper (15 questions: 5x2m, 5x3m, 5x5m).
2. Strict English-medium enforcement: zero Tamil characters in question stems.
3. Zero raw URLs (http://, https://, www.) in questions.
4. Zero textbook bibliography / publisher / citation metadata.
5. Zero generic template / boilerplate prompts.
6. Continuous sequential numbering across Section A, B, and C.
7. Total marks equal 50 and question count equals 15.
8. PDF generation and text integrity verification.
"""

import unittest
import json
import os
import re
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import SessionLocal
from database.models import User, Question, GeneratedPaper
from services.auth import create_access_token
from services.question_selection import is_invalid_question_content, is_vague_question


class TestClass10ScienceEnglishPaperQuality(unittest.TestCase):
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

    def test_01_c10_science_50mark_english_paper_generation(self):
        """
        Verify end-to-end generation of a 50-mark Class 10 Science paper:
        Section A: 5 x 2 marks = 10 marks
        Section B: 5 x 3 marks = 15 marks
        Section C: 5 x 5 marks = 25 marks
        Total: 15 questions, 50 marks.
        """
        payload = {
            'title': 'Science Terminal Examination 2026',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'board': 'Tamil Nadu State Board',
            'language': 'English',
            'total_marks': 50,
            'num_questions': 15,
            'duration_minutes': 150,
            'sections': [
                {'label': 'A', 'marks_per_question': 2, 'num_questions': 5, 'title': '2-MARK QUESTIONS'},
                {'label': 'B', 'marks_per_question': 3, 'num_questions': 5, 'title': '3-MARK QUESTIONS'},
                {'label': 'C', 'marks_per_question': 5, 'num_questions': 5, 'title': '5-MARK QUESTIONS'},
            ]
        }

        resp = self.client.post('/api/generate-paper', data=json.dumps(payload), headers=self.headers)
        self.assertEqual(resp.status_code, 201, f"Failed to generate paper: {resp.get_data(as_text=True)}")

        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('count'), 15)
        self.assertEqual(data.get('total_marks'), 50)

        questions = data.get('questions', [])
        self.assertEqual(len(questions), 15)

        # Verify sequential numbering 1 to 15
        numbers = [q.get('display_number') for q in questions]
        self.assertEqual(numbers, list(range(1, 16)))

        # Verify section mark totals
        sections = data.get('sections', [])
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0]['total_section_marks'], 10)
        self.assertEqual(sections[1]['total_section_marks'], 15)
        self.assertEqual(sections[2]['total_section_marks'], 25)

        # Verify every question satisfies quality constraints
        for idx, q in enumerate(questions, 1):
            q_text = q.get('question', '')
            self.assertTrue(len(q_text) >= 10, f"Question {idx} too short: '{q_text}'")

            # No Tamil characters
            has_tamil = any('\u0b80' <= ch <= '\u0bff' for ch in q_text)
            self.assertFalse(has_tamil, f"Question {idx} contains Tamil characters: '{q_text}'")

            # No raw URLs
            has_url = bool(re.search(r'https?://|www\.', q_text))
            self.assertFalse(has_url, f"Question {idx} contains raw URL: '{q_text}'")

            # No bibliography / publisher citations
            invalid, reason = is_invalid_question_content(q_text, target_language='English')
            self.assertFalse(invalid, f"Question {idx} invalid: {reason} ('{q_text}')")

            # No vague template prompts
            vague, v_reason = is_vague_question(q_text)
            self.assertFalse(vague, f"Question {idx} matches vague template: {v_reason} ('{q_text}')")

    def test_02_pdf_file_integrity_and_rendering(self):
        """
        Verify that the generated paper creates a valid printable PDF on disk
        with official headers and clean layout.
        """
        payload = {
            'title': 'Mid-Term Science Exam 2026',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'board': 'Tamil Nadu State Board',
            'total_marks': 50,
            'num_questions': 15,
            'duration_minutes': 180,
            'sections': [
                {'label': 'A', 'marks_per_question': 2, 'num_questions': 5},
                {'label': 'B', 'marks_per_question': 3, 'num_questions': 5},
                {'label': 'C', 'marks_per_question': 5, 'num_questions': 5},
            ]
        }

        resp = self.client.post('/api/generate-paper', data=json.dumps(payload), headers=self.headers)
        self.assertEqual(resp.status_code, 201)

        data = resp.get_json()
        pdf_filename = data.get('pdf_filename')
        self.assertIsNotNone(pdf_filename)

        from config import Config
        pdf_path = os.path.join(Config.GENERATED_PAPERS_DIR, pdf_filename)
        self.assertTrue(os.path.exists(pdf_path), f"PDF file not found at {pdf_path}")
        self.assertGreater(os.path.getsize(pdf_path), 2000, "PDF file too small")

        # Verify PDF header magic bytes
        with open(pdf_path, 'rb') as f:
            header = f.read(5)
            self.assertEqual(header, b'%PDF-')

    def test_03_quality_filter_rejects_url_citation_and_tamil_for_english(self):
        """
        Unit test for is_invalid_question_content.
        """
        # URLs must be rejected
        self.assertTrue(is_invalid_question_content('http://www.tutorvista.com/')[0])
        self.assertTrue(is_invalid_question_content('Visit www.sciencedaily.com for more info')[0])

        # Citations must be rejected
        self.assertTrue(is_invalid_question_content('Pandey B.P.Plant Anatomy, S.Chand and Company Ltd, New Delhi')[0])
        self.assertTrue(is_invalid_question_content('B.S.Tomar, An Introduction to General Biology, 9th Edition, Rastogi Publications')[0])

        # Tamil characters must be rejected for English target
        self.assertTrue(is_invalid_question_content('தாவரங்கள் எவ்வாறு நீரை உறிஞ்சுகின்றன. விவரி.', target_language='English')[0])

        # Clean English science questions must be accepted
        self.assertFalse(is_invalid_question_content('State Newton\'s second law of motion and derive F = ma.', target_language='English')[0])
        self.assertFalse(is_invalid_question_content('Explain the refraction of light through a triangular glass prism.', target_language='English')[0])


if __name__ == '__main__':
    unittest.main()

