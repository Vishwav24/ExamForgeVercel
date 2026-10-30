"""
Comprehensive Verification Tests for Standards 6 to 12 Textbook Extraction Pipeline
and Multi-Standard Paper Generation Integrity.

Covers:
1. Multi-standard extraction verification (Classes 6, 7, 8, 9, 10, 11, 12).
2. Bilingual medium coverage (Tamil and English mediums).
3. Unicode NFC preservation and Tamil character integrity.
4. Filtering of non-evaluative content (learning objectives, activities, solved problems).
5. Candidate staging schema and uncertainty flagging.
6. Zero mutation guarantee: no candidate questions imported into live database.
7. Representative paper-generation and selection regression tests across all 7 classes.
"""

import os
import sys
import json
import sqlite3
import unicodedata
import unittest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import SessionLocal
from database.models import User, Question
from services.auth import create_access_token, hash_password
from services.question_selection import select_questions


class TestStandards6To12Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.db = SessionLocal()
        cls.candidates_dir = os.path.join(backend_dir, 'data', 'extracted_candidates')
        cls.json_path = os.path.join(cls.candidates_dir, 'candidates_all_standards.json')
        cls.report_path = os.path.join(cls.candidates_dir, 'coverage_report.json')
        cls.db_path = os.path.join(backend_dir, 'database', 'examforge.db')
        
        # Load extracted candidates
        cls.has_candidates = os.path.exists(cls.json_path)
        if cls.has_candidates:
            with open(cls.json_path, 'r', encoding='utf-8') as f:
                cls.candidates = json.load(f)
        else:
            cls.candidates = []

        # Ensure an admin/principal user exists for authenticated requests
        cls.admin_user = cls.db.query(User).filter_by(role='admin').first()
        if not cls.admin_user:
            cls.admin_user = User(
                email='principal.test@examforge.ai',
                password_hash=hash_password('Principal@2026'),
                full_name='Principal Test',
                role='admin',
                is_active=True
            )
            cls.db.add(cls.admin_user)
            cls.db.commit()
            cls.db.refresh(cls.admin_user)
            
        cls.token = create_access_token(cls.admin_user)
        cls.headers = {'Authorization': f'Bearer {cls.token}', 'Content-Type': 'application/json'}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_all_seven_standards_present_in_candidates(self):
        """Verify candidate questions exist for all seven standards: Class 6 through 12."""
        self.assertTrue(self.has_candidates, "Candidates JSON file must exist")
        self.assertGreater(len(self.candidates), 10000, "Should have extracted a substantial candidate pool")
        
        classes_found = {c['class_grade'] for c in self.candidates}
        expected_classes = {'Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12'}
        
        for expected in expected_classes:
            self.assertIn(expected, classes_found, f"Missing candidate questions for {expected}")
            count_for_class = sum(1 for c in self.candidates if c['class_grade'] == expected)
            self.assertGreaterEqual(count_for_class, 500, f"{expected} should have at least 500 candidate questions")

    def test_02_bilingual_coverage_tamil_and_english(self):
        """Verify candidate questions are present in both Tamil and English mediums."""
        mediums = {c['medium'] for c in self.candidates}
        self.assertIn('Tamil', mediums, "Must have Tamil medium candidates")
        self.assertIn('English', mediums, "Must have English medium candidates")
        
        tamil_count = sum(1 for c in self.candidates if c['medium'] == 'Tamil')
        english_count = sum(1 for c in self.candidates if c['medium'] == 'English')
        
        self.assertGreater(tamil_count, 5000, "Should have strong Tamil medium representation")
        self.assertGreater(english_count, 5000, "Should have strong English medium representation")

    def test_03_tamil_unicode_preservation_and_nfc_normalization(self):
        """Verify Tamil text characters are NFC-normalized without corrupt replacements."""
        tamil_cands = [c for c in self.candidates if c['medium'] == 'Tamil']
        self.assertGreater(len(tamil_cands), 0)
        
        sample_size = min(200, len(tamil_cands))
        for cand in tamil_cands[:sample_size]:
            text = cand['question_text']
            # Zero-width joiner, BOM, and replacement char checks
            self.assertNotIn('\u200c', text, "Zero-width non-joiner should be stripped")
            self.assertNotIn('\ufeff', text, "BOM should be stripped")
            self.assertNotIn('\ufffd', text, "Corrupt replacement char found")
            self.assertEqual(text, unicodedata.normalize('NFC', text), "Text must be NFC normalized")

    def test_04_learning_objectives_and_non_evaluative_content_excluded(self):
        """Verify learning objectives and non-evaluative markers were not extracted as questions."""
        forbidden_snippets = [
            'கற்றல் நோக்கங்கள்', 'கற்பவை கற்றபின்', 'learning objectives',
            'points to remember', 'பாடலின் பொருள்'
        ]
        for c in self.candidates[:500]:
            stem_lower = c['question_text'].lower()
            for forb in forbidden_snippets:
                self.assertNotIn(forb, stem_lower, f"Non-evaluative snippet '{forb}' should not be in question stem")

    def test_05_staging_candidate_schema_and_flags(self):
        """Verify required schema fields and that uncertain items are flagged rather than dropped."""
        required_keys = [
            'candidate_id', 'class_grade', 'subject', 'medium', 'term', 'edition',
            'source_file', 'source_line_start', 'unit_or_chapter', 'section_heading',
            'question_type', 'suggested_marks', 'bloom_level', 'question_text',
            'options', 'validation_status', 'uncertainty_reason'
        ]
        sample = self.candidates[0]
        for k in required_keys:
            self.assertIn(k, sample, f"Missing key '{k}' in candidate schema")
            
        # Verify bloom_level is None/unassigned to avoid fabricating ground truth
        self.assertIsNone(sample['bloom_level'], "Bloom level must not be fabricated from textbook source")
        
        # Verify uncertainty flags exist in the dataset
        uncertain_cands = [c for c in self.candidates if c['validation_status'] == 'uncertain']
        self.assertGreater(len(uncertain_cands), 0, "Uncertain items should be flagged with an audit reason")
        for uc in uncertain_cands[:10]:
            self.assertTrue(len(uc['uncertainty_reason']) > 0, "Flagged uncertain item must have a documented reason")

    def test_06_live_database_has_zero_unreviewed_candidates(self):
        """Verify that all questions in the live database have verified status."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM questions WHERE verified = 0 AND board = 'Tamil Nadu State Board'")
        unverified_count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(unverified_count, 0, "Zero unreviewed questions should exist in live TNSB questions")

    def test_07_paper_generation_selection_class_6_to_12(self):
        """
        Verify the Question Selection Service behavior across all seven standards (Class 6-12).
        Tests that:
        1. When questions exist for available marks in DB, paper generation succeeds via API.
        2. When questions are genuinely insufficient, exact shortage message is returned.
        3. Zero cross-contamination across classes or subjects.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Iterate over all 7 classes
        for grade_num in range(6, 13):
            class_name = f"Class {grade_num}"
            cur.execute("""
                SELECT subject, topic, marks, COUNT(*) 
                FROM questions 
                WHERE class_grade = ? 
                GROUP BY subject, topic, marks 
                HAVING COUNT(*) >= 2
                LIMIT 1
            """, (class_name,))
            row = cur.fetchone()
            
            if row:
                subject, topic, marks, available = row
                marks_int = int(marks)
                payload = {
                    'title': f'{class_name} Unit Assessment',
                    'board': 'Tamil Nadu State Board',
                    'class_grade': class_name,
                    'subject': subject,
                    'chapters': [topic],
                    'total_marks': marks_int * 2,
                    'duration_minutes': 45,
                    'sections': [
                        {
                            'label': 'Part A',
                            'marks_per_question': marks_int,
                            'num_questions': 2
                        }
                    ]
                }
                resp = self.client.post('/api/papers/generate', json=payload, headers=self.headers)
                self.assertIn(
                    resp.status_code, [200, 201], 
                    f"Paper generation failed for {class_name} {subject} with status {resp.status_code}: {resp.get_data(as_text=True)}"
                )
                data = resp.get_json()
                self.assertTrue(data.get('success', False))
                returned_questions = data.get('questions', [])
                self.assertEqual(len(returned_questions), 2)
                for q in returned_questions:
                    self.assertEqual(q['class_grade'], class_name)
                    self.assertEqual(q['subject'], subject)
                    self.assertEqual(q['marks'], marks_int)

        # Test shortage enforcement: requesting non-existent 1-mark question in Class 10 Tamil
        shortage_payload = {
            'title': 'Tamil Shortage Test',
            'board': 'Tamil Nadu State Board',
            'class_grade': 'Class 10',
            'subject': 'Tamil',
            'chapters': ['அன்னை மொழியே'],
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
        shortage_resp = self.client.post('/api/papers/generate', json=shortage_payload, headers=self.headers)
        self.assertEqual(shortage_resp.status_code, 400)
        shortage_data = shortage_resp.get_json()
        self.assertFalse(shortage_data['success'])
        self.assertIn("Insufficient questions for Section A", shortage_data['error'])
        self.assertIn("Need 5 more 1-mark question(s)", shortage_data['error'])
        self.assertIn("Available: 0, Required: 5", shortage_data['error'])

        conn.close()


if __name__ == '__main__':
    unittest.main()
