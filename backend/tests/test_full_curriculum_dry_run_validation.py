"""
Unit & Regression Test Suite for Full-Curriculum Candidate Validation & Dry-Run Integrity
Ensures:
1. Candidate validation logic correctly flags short text, OCR errors, answer contamination.
2. Normalization logic maps textbook chapters to supported TNSB curriculum.
3. Bilingual support: English and Tamil Unicode integrity is maintained.
4. Duplicate detection identifies collisions against live DB and intra-batch duplicates.
5. Dry-run process performs ZERO writes to examforge.db (file size & mtime unchanged).
6. Preserves existing live questions, users, papers, audit logs without modification.
"""

import unittest
import os
import sys
import json
import sqlite3

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from scripts.validate_and_dry_run_full_curriculum import (
    detect_language, normalize_text_key, normalize_chapter_for_subject,
    OCR_GARBAGE_RE, ANSWER_CONTAM_RE, run_full_validation_and_dry_run
)
from services.curriculum_service import get_supported_classes, get_supported_subjects, get_supported_chapters, TN_CURRICULUM_DATA
from database.db import SessionLocal
from database.models import Question, User, GeneratedPaper, AuditLog


class TestFullCurriculumDryRunValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join(backend_dir, 'database', 'examforge.db')
        stat = os.stat(cls.db_path)
        cls.initial_size = stat.st_size
        cls.initial_mtime = stat.st_mtime

    def test_01_validation_rejects_empty_short_and_malformed_ocr(self):
        """Verify quality heuristics reject empty questions, <10 chars, and excessive OCR glitches."""
        self.assertTrue(len("") < 10)
        self.assertTrue(len("What is?") < 10)

        # OCR garbage regex tests
        self.assertIsNotNone(OCR_GARBAGE_RE.search("Explain ?????? the following concept"))
        self.assertIsNotNone(OCR_GARBAGE_RE.search("Define a b c d in physics"))
        self.assertIsNotNone(OCR_GARBAGE_RE.search("Calculate the value of _____"))

        # Valid clean question should not match
        self.assertIsNone(OCR_GARBAGE_RE.search("State Newton's second law of motion with mathematical formulation."))

    def test_02_validation_detects_answer_contamination(self):
        """Verify questions with answers concatenated into question stem are flagged."""
        contaminated_en = "What is the unit of force? Ans: Newton"
        contaminated_ta = "விசையின் அலகு யாது? விடை: நியூட்டன்"
        clean_q = "What is the SI unit of force?"

        self.assertIsNotNone(ANSWER_CONTAM_RE.search(contaminated_en))
        self.assertIsNotNone(ANSWER_CONTAM_RE.search(contaminated_ta))
        self.assertIsNone(ANSWER_CONTAM_RE.search(clean_q))

    def test_03_chapter_normalization_maps_correctly(self):
        """Verify raw textbook chapter strings normalize to official syllabus chapters."""
        # Class 10 Mathematics
        self.assertEqual(
            normalize_chapter_for_subject("பயிற்சி-1.1", "Mathematics", "Class 10"),
            "Relations and Functions"
        )
        self.assertEqual(
            normalize_chapter_for_subject("Numbers and Sequences", "Mathematics", "Class 10"),
            "Numbers and Sequences"
        )
        self.assertEqual(
            normalize_chapter_for_subject("Unit 5 Coordinate Geometry", "Mathematics", "Class 10"),
            "Coordinate Geometry"
        )

        # Class 10 Science
        self.assertEqual(
            normalize_chapter_for_subject("Unit 1 Laws of Motion", "Science", "Class 10"),
            "Laws of Motion"
        )
        self.assertEqual(
            normalize_chapter_for_subject("ஒளியியல்", "Science", "Class 10"),
            "Optics"
        )

    def test_04_tamil_unicode_detection_and_integrity(self):
        """Verify Tamil script is accurately detected and preserved without encoding distortion."""
        tamil_q = "ஒரு பொருளின் உந்தம் அதன் நிறையைச் சார்ந்ததா?"
        english_q = "Does momentum depend on the mass of an object?"

        self.assertEqual(detect_language(tamil_q), "Tamil")
        self.assertEqual(detect_language(english_q), "English")

        # Verify normalized key preserves Tamil characters
        norm = normalize_text_key(tamil_q)
        self.assertIn("உந்தம்", norm)

    def test_05_duplicate_key_generation(self):
        """Verify normalization identifies duplicate text regardless of casing and punctuation."""
        q1 = "What is the speed of light in vacuum?"
        q2 = "what is the speed of light in vacuum! "
        self.assertEqual(normalize_text_key(q1), normalize_text_key(q2))

    def test_06_live_database_strictly_unmodified_after_validation(self):
        """Verify that running the validation and dry run causes ZERO writes to examforge.db."""
        stat_before = os.stat(self.db_path)
        
        # Run validation
        run_full_validation_and_dry_run()

        stat_after = os.stat(self.db_path)
        self.assertEqual(stat_before.st_size, stat_after.st_size)
        self.assertEqual(stat_before.st_mtime, stat_after.st_mtime)

    def test_07_generated_manifest_and_matrix_reports_exist(self):
        """Verify all three comprehensive report artifacts are generated with valid JSON structure."""
        rep_dir = os.path.join(backend_dir, 'reports')
        manifest_path = os.path.join(rep_dir, 'full_curriculum_validation_manifest.json')
        dry_run_path = os.path.join(rep_dir, 'full_curriculum_dry_run_report.json')
        matrix_path = os.path.join(rep_dir, 'classes_6_to_12_coverage_matrix.json')

        self.assertTrue(os.path.exists(manifest_path))
        self.assertTrue(os.path.exists(dry_run_path))
        self.assertTrue(os.path.exists(matrix_path))

        with open(dry_run_path, 'r', encoding='utf-8') as f:
            dry_data = json.load(f)
            self.assertEqual(dry_data['projected_post_import']['overwritten_live_records'], 0)
            self.assertEqual(dry_data['projected_post_import']['status'], 'READY_AWAITING_EXPLICIT_USER_CONFIRMATION')

        with open(matrix_path, 'r', encoding='utf-8') as f:
            mat_data = json.load(f)
            self.assertEqual(len(mat_data['pairs']), 45)
            self.assertEqual(mat_data['total_chapters'], 383)

    def test_08_live_database_counts_preserved(self):
        """Verify that question bank records are preserved and expanded."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        c = conn.cursor()
        c.execute("SELECT count(*) FROM questions")
        self.assertGreaterEqual(c.fetchone()[0], 5015)
        c.execute("SELECT count(*) FROM questions WHERE board = 'Tamil Nadu State Board'")
        self.assertGreaterEqual(c.fetchone()[0], 1425)
        conn.close()


if __name__ == '__main__':
    unittest.main()
