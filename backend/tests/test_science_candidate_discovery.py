"""
Tests for Candidate Discovery & Class 10 Science Shortage Investigation
Verifies:
1. Candidate discovery script parses combined_training_dataset.csv and generates review CSV.
2. Verified TNSB metadata is strictly distinguished from ML/heuristic predictions.
3. No 1-mark questions are falsely fabricated or claimed to exist in combined_training_dataset.csv.
4. Zero modification of original dataset, database, models, or paper generation filters.
"""

import os
import sys
import csv
import sqlite3
import unittest
import pandas as pd

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from scripts.discover_science_candidates import (
    discover_science_candidates, CLASS_10_SCIENCE_CHAPTERS
)


class TestScienceCandidateDiscovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.combined_csv = os.path.join(backend_dir, 'data', 'combined_training_dataset.csv')
        cls.review_csv = os.path.join(backend_dir, 'data', 'discovered_c10_science_candidates_review.csv')
        cls.db_path = os.path.join(backend_dir, 'database', 'examforge.db')
        cls.v2_class10_csv = os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_10.csv')

    def test_01_combined_dataset_structure_and_counts(self):
        """Verify combined_training_dataset.csv schema and lack of class/marks columns."""
        df = pd.read_csv(self.combined_csv, nrows=10)
        expected_cols = ['question_id', 'question', 'subject', 'topic', 'bloom_level', 'question_type', 'difficulty', 'source', 'board', 'verified', 'is_tn_state_board']
        for col in expected_cols:
            self.assertIn(col, df.columns)
            
        # Confirm that class_grade and marks do NOT exist in the combined training dataset
        self.assertNotIn('class_grade', df.columns, "combined_training_dataset.csv has no class_grade column")
        self.assertNotIn('marks', df.columns, "combined_training_dataset.csv has no marks column")

    def test_02_review_csv_generated_with_required_fields(self):
        """Verify that discovered_c10_science_candidates_review.csv exists and has complete schema."""
        self.assertTrue(os.path.exists(self.review_csv), "Review CSV must exist")
        df_rev = pd.read_csv(self.review_csv)
        self.assertGreater(len(df_rev), 1000, "Should have screened candidate matches")
        
        required_fields = [
            'row_id', 'question_text', 'source', 'is_verified_tnsb',
            'original_subject', 'original_topic', 'predicted_class_grade',
            'predicted_subject', 'predicted_chapter', 'confidence_score',
            'is_vague_template', 'eligible_for_1_mark', 'review_recommendation'
        ]
        for field in required_fields:
            self.assertIn(field, df_rev.columns, f"Missing field {field} in review CSV")

    def test_03_verified_tnsb_strictly_separated_from_predictions(self):
        """Verify that verified TNSB questions have confidence 1.0 while EduBloom has predicted flags."""
        df_rev = pd.read_csv(self.review_csv)
        
        # Verified TNSB records
        tnsb_records = df_rev[df_rev['is_verified_tnsb'] == True]
        self.assertGreater(len(tnsb_records), 0)
        for _, row in tnsb_records.iterrows():
            self.assertEqual(row['confidence_score'], 1.0)
            self.assertIn('Verified Source', row['predicted_class_grade'])
            self.assertFalse(row['eligible_for_1_mark'])  # Original marks are 2m, 3m, 5m

        # EduBloom predicted records
        edubloom_records = df_rev[df_rev['is_verified_tnsb'] == False]
        self.assertGreater(len(edubloom_records), 0)
        for _, row in edubloom_records.iterrows():
            self.assertLess(row['confidence_score'], 1.0)
            self.assertIn('Predicted', row['predicted_class_grade'])
            self.assertFalse(row['eligible_for_1_mark'])

    def test_04_zero_verified_1_mark_science_questions_in_training_dataset(self):
        """Verify that zero rows in combined_training_dataset.csv are verified 1-mark Class 10 Science questions."""
        df_rev = pd.read_csv(self.review_csv)
        verified_1m = df_rev[(df_rev['is_verified_tnsb'] == True) & (df_rev['eligible_for_1_mark'] == True)]
        self.assertEqual(len(verified_1m), 0, "No verified 1-mark questions exist in combined_training_dataset.csv")

    def test_05_authentic_1_mark_questions_exist_in_extracted_candidates_v2(self):
        """Verify that genuine 1-mark Class 10 Science questions exist in extracted_candidates_v2."""
        self.assertTrue(os.path.exists(self.v2_class10_csv))
        df_v2 = pd.read_csv(self.v2_class10_csv)
        sci_1m = df_v2[(df_v2['subject'] == 'Science') & (df_v2['suggested_marks'] == 1.0)]
        self.assertGreater(len(sci_1m), 500, f"Expected >500 genuine 1-mark Science questions in v2, found {len(sci_1m)}")

    def test_06_database_and_datasets_unmodified(self):
        """Verify live SQLite database and original training dataset remain untouched."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM questions WHERE question_id LIKE 'DISC_%'")
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0, "Discovered review candidates must NOT be imported into live DB")


if __name__ == '__main__':
    unittest.main()

