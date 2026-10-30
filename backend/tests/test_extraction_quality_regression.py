"""
Regression Tests: Extraction Quality Improvements (v2 Engine)
Validates:
1. Class 10 Tamil composite exercise isolation and activity exclusion.
2. Answer key separation into dedicated answer_text field (விடை:, Answer:, etc.).
3. Subject classification accuracy (Biochemistry vs Chemistry, Business Maths, Vocational).
4. Type and marks consistency (no short_answer with 1 mark, no objective with >1 mark).
5. Versioned output preservation (v1 and v2 directories coexisting).
"""

import os
import sys
import json
import sqlite3
import unittest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from services.textbook_extractor import (
    TextbookExtractor, separate_answer_text, separate_inline_options, resolve_subject
)


class TestExtractionQualityRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1_dir = os.path.join(backend_dir, 'data', 'extracted_candidates')
        cls.v2_dir = os.path.join(backend_dir, 'data', 'extracted_candidates_v2')
        cls.v2_json = os.path.join(cls.v2_dir, 'candidates_all_standards.json')
        cls.report_path = os.path.join(backend_dir, 'reports', 'extraction_quality_improvement_report.md')
        cls.db_path = os.path.join(backend_dir, 'database', 'examforge.db')

        cls.v2_candidates = []
        if os.path.exists(cls.v2_json):
            with open(cls.v2_json, 'r', encoding='utf-8') as f:
                cls.v2_candidates = json.load(f)

    def test_01_versioned_directories_coexist(self):
        """Verify that v1 directory is preserved and v2 directory exists."""
        self.assertTrue(os.path.exists(self.v1_dir), "Original v1 output directory must be preserved")
        self.assertTrue(os.path.exists(self.v2_dir), "Versioned v2 output directory must exist")
        self.assertTrue(os.path.exists(os.path.join(self.v1_dir, 'candidates_all_standards.json')))
        self.assertTrue(os.path.exists(self.v2_json))

    def test_02_subject_resolution_biochemistry_vs_chemistry(self):
        """Verify that Bio_Chemistry is accurately resolved to Biochemistry, not Chemistry."""
        # Test unit function
        self.assertEqual(
            resolve_subject('Class_12_Bio_Chemistry_English_Medium-2024_Edition.md', '12th-standard/English/...'),
            'Biochemistry'
        )
        self.assertEqual(
            resolve_subject('Class_12_Chemistry_English_Medium-Volume_1-2024_Edition.md', '12th-standard/English/...'),
            'Chemistry'
        )
        self.assertEqual(
            resolve_subject('Class_11_Business_Mathematics_and_Statistics_English_Medium.md', '11th-standard/...'),
            'Business Mathematics & Statistics'
        )
        self.assertEqual(
            resolve_subject('Class_11_Basic_Automobile_Engineering_English_Medium-2024_Edition.md', '11th-standard/...'),
            'Automobile Engineering'
        )

        # Test extracted v2 candidates
        biochem_cands = [c for c in self.v2_candidates if 'Bio_Chemistry' in c['source_file']]
        self.assertGreater(len(biochem_cands), 0)
        for c in biochem_cands:
            self.assertEqual(c['subject'], 'Biochemistry', f"Candidate from {c['source_file']} must be Biochemistry, not Chemistry")

    def test_03_answer_text_separation(self):
        """Verify that answer text (விடை:, Answer:) is separated into answer_text and removed from stem."""
        # Unit test on sample strings
        sample_tam = "பின்வரும் கூற்றுகளில் ஒரு செல் சவ்வின் பங்கை விளக்கும் கூற்று எது? விடை : ஆ. செல்லின்வழியாக பொருட்கள் கட்டுபடுத்தப்பட்ட இயக்கத்தின் மூலம் நகருகின்றன ."
        stem_tam, ans_tam = separate_answer_text(sample_tam)
        self.assertNotIn("விடை", stem_tam)
        self.assertIsNotNone(ans_tam)
        self.assertIn("செல்லின்வழியாக", ans_tam)

        sample_eng = "dashdash_statement describes the role of a cell membrane ? (Answer B) controlled movement of substances across the cell."
        stem_eng, ans_eng = separate_answer_text(sample_eng)
        self.assertNotIn("Answer", stem_eng)
        self.assertIsNotNone(ans_eng)
        self.assertIn("controlled movement", ans_eng)

        # Dataset-level check: v2 candidates should not contain answer labels in stems
        ans_in_stem = [
            c for c in self.v2_candidates 
            if any(k in c['question_text'] for k in ['விடை :', 'விடை:', 'Answer:', '(Answer'])
        ]
        self.assertEqual(len(ans_in_stem), 0, f"Found {len(ans_in_stem)} candidates with unseparated answer text in stem")

    def test_04_class_10_tamil_composite_exercise_isolation(self):
        """Verify that classroom activities and poetry writing are not merged into question stems."""
        # Find candidates around Class 10 Tamil line 1095
        cands_10_tam = [c for c in self.v2_candidates if c['class_grade'] == 'Class 10' and c['subject'] == 'Tamil']
        self.assertGreater(len(cands_10_tam), 0)

        # Ensure no candidate has markdown table artifacts or activities merged
        for c in cands_10_tam:
            t = c['question_text']
            self.assertNotIn('| --- |', t, "Markdown table artifact found merged in question stem")
            self.assertNotIn('####', t, "Markdown heading found inside question stem")
            self.assertNotIn('மொழியோடு விளையாடு', t, "Language game activity merged into question stem")
            self.assertNotIn('செயல் திட்டம்', t, "Project activity merged into question stem")
            self.assertNotIn('நிற்க அதற்குத் தக', t, "Moral activity merged into question stem")

    def test_05_strict_type_and_marks_consistency(self):
        """Verify that no candidate has inconsistent type-marks pairings (e.g. short_answer with 1 mark)."""
        inconsistent = []
        for c in self.v2_candidates:
            q_type = c['question_type']
            marks = c['suggested_marks']
            if q_type == 'short_answer' and marks == 1:
                inconsistent.append(c)
            elif q_type == 'objective' and marks and marks > 1:
                inconsistent.append(c)
            elif q_type == 'long_answer' and marks and marks < 4:
                inconsistent.append(c)

        self.assertEqual(
            len(inconsistent), 0,
            f"Found {len(inconsistent)} candidates with type/marks inconsistency"
        )

    def test_06_database_remains_unmodified(self):
        """Verify that all questions in the live database have verified status."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM questions WHERE verified = 0 AND board = 'Tamil Nadu State Board'")
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0, "No unverified questions should be present in live database")


if __name__ == '__main__':
    unittest.main()

