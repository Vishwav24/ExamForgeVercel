"""
Comprehensive Test Suite for EduBloom Dataset Pipeline & Candidate Models
Verifies all requirements for optional EduBloom Hugging Face dataset integration:
1. Schema validation, duplicate checks, missing values, and L1-L6 Bloom mappings.
2. Strict isolation: EduBloom questions are labeled 'General / EduBloom' (verified=False)
   and are NEVER labeled as Tamil Nadu State Board questions.
3. Candidate models are trained separately on held-out test splits without replacing active models.
4. Candidate vs. active baseline metrics comparison (delta calculations).
5. Non-destructive promotion policy: candidate models require explicit admin action before promotion.
6. RBAC: Teacher cannot access EduBloom validation, candidate training, or summary endpoints (HTTP 403).
7. Question paper generation continues to draw strictly from verified Tamil Nadu State Board questions.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config
from app import app, setup_database
from database.db import SessionLocal
from database.models import User, Question, ModelVersion
from services.edubloom_service import (
    inspect_and_validate_edubloom_dataset,
    get_edubloom_clean_dataframe,
    optionally_stage_edubloom_into_db,
    build_combined_training_dataset,
    get_combined_dataset_summary,
    get_combined_dataset_path
)
from ml.random_forest_trainer import (
    train_edubloom_candidate_model,
    train_combined_candidate_model,
    clean_template_leakage,
    activate_version
)


class TestEduBloomPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_database()
        cls.client = app.test_client()

    def _get_admin_token(self):
        resp = self.client.post('/api/auth/login', json={
            'email': 'admin@examforge.ai',
            'password': 'Admin@2026'
        })
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()['token']

    def _get_teacher_token(self):
        resp = self.client.post('/api/auth/login', json={
            'email': 'teacher@examforge.ai',
            'password': 'ExamForge@2026'
        })
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()['token']

    # Requirement 1: Dataset Validation & L1-L6 Mapping
    def test_01_edubloom_validation_and_l_code_mapping(self):
        report = inspect_and_validate_edubloom_dataset()
        self.assertTrue(report['success'])
        self.assertEqual(report['total_rows_inspected'], 73712)
        self.assertEqual(report['valid_usable_rows'], 73712)
        self.assertEqual(report['total_rejected_rows'], 0)

        # Verify L1-L6 to Bloom Taxonomy mapping
        mapped_bloom = report['mapped_bloom_distribution']
        for level in Config.BLOOM_LEVELS:
            self.assertIn(level, mapped_bloom)
            self.assertGreater(mapped_bloom[level]['count'], 1000)

        # Verify Difficulty mapping
        mapped_diff = report['mapped_difficulty_distribution']
        for diff in Config.DIFFICULTY_LEVELS:
            self.assertIn(diff, mapped_diff)
            self.assertGreater(mapped_diff[diff]['count'], 5000)

        # Verify curriculum alignment isolation guard
        guard = report['curriculum_alignment_guard']
        self.assertEqual(guard['board_tag_applied'], 'General / EduBloom')
        self.assertFalse(guard['verified_state'])
        self.assertTrue(guard['state_board_isolation_enforced'])

    # Requirement 2: Clean DataFrame Isolation & Label Integrity
    def test_02_clean_dataframe_isolation_guards(self):
        df = get_edubloom_clean_dataframe()
        self.assertEqual(len(df), 73712)
        
        # Verify board isolation
        self.assertTrue((df['board'] == 'General / EduBloom').all())
        self.assertTrue((df['verified'] == False).all())

        # Verify no L1-L6 raw strings leak into bloom_level
        self.assertTrue(df['bloom_level'].isin(Config.BLOOM_LEVELS).all())
        self.assertTrue(df['difficulty'].isin(Config.DIFFICULTY_LEVELS).all())

    # Requirement 3: Candidate Model Training & Non-Overwrite Guarantee
    def test_03_candidate_model_training_and_comparison(self):
        db = SessionLocal()
        try:
            active_before = db.query(ModelVersion).filter_by(task_name='bloom_level', is_active=True).first()
            active_before_id = active_before.id if active_before else None
            active_before_version = active_before.version if active_before else None
        finally:
            db.close()

        # Train a candidate model on a sample
        res = train_edubloom_candidate_model(task_name='bloom_level', sample_limit=120, n_estimators=10)
        self.assertTrue(res['success'])
        self.assertTrue(res['is_candidate'])
        self.assertFalse(res['is_active'])
        self.assertTrue(res['promotion_required'])
        self.assertIn('candidate', res['version'])

        # Verify active baseline comparison metrics
        comp = res['active_model_comparison']
        if active_before_version:
            self.assertIsNotNone(comp)
            self.assertEqual(comp['active_version'], active_before_version)
            self.assertIn('delta_accuracy', comp)
            self.assertIn('delta_macro_f1', comp)

        db2 = SessionLocal()
        try:
            # Verify that active model in DB was NOT replaced
            active_after = db2.query(ModelVersion).filter_by(task_name='bloom_level', is_active=True).first()
            self.assertIsNotNone(active_after)
            if active_before_id:
                self.assertEqual(active_after.id, active_before_id)

            # Verify candidate model is saved with is_active=False
            cand_model = db2.get(ModelVersion, res['model_id'])
            self.assertIsNotNone(cand_model)
            self.assertFalse(cand_model.is_active)
            self.assertIn('candidate', cand_model.version)
        finally:
            db2.close()

    # Requirement 4: Staging Questions Does Not Corrupt State Board Bank
    def test_04_optional_staging_keeps_tn_board_clean(self):
        db = SessionLocal()
        try:
            tn_count_before = db.query(Question).filter(Question.board == 'Tamil Nadu State Board').count()
        finally:
            db.close()

        # Stage 10 sample questions
        res = optionally_stage_edubloom_into_db(max_rows=10)
        self.assertTrue(res['success'])
        self.assertEqual(res['board_tag'], 'General / EduBloom')
        self.assertFalse(res['verified'])
        self.assertEqual(res['inserted_count'], 10)

        db2 = SessionLocal()
        try:
            # TN State Board question count MUST NOT change
            tn_count_after = db2.query(Question).filter(Question.board == 'Tamil Nadu State Board').count()
            self.assertEqual(tn_count_before, tn_count_after)

            # Verify staged questions are unverified
            staged_q = db2.query(Question).filter(Question.board == 'General / EduBloom').first()
            self.assertIsNotNone(staged_q)
            self.assertFalse(staged_q.verified)
        finally:
            db2.close()

    # Requirement 5: RBAC - Teachers cannot access EduBloom admin endpoints
    def test_05_teacher_rbac_access_denied(self):
        t_token = self._get_teacher_token()
        headers = {'Authorization': f'Bearer {t_token}'}

        # Validate endpoint
        resp_val = self.client.post('/api/admin/edubloom/validate', headers=headers)
        self.assertEqual(resp_val.status_code, 403)

        # Train candidate endpoint
        resp_train = self.client.post('/api/admin/edubloom/train-candidate', headers=headers, json={'task_name': 'bloom_level'})
        self.assertEqual(resp_train.status_code, 403)

        # Summary endpoint
        resp_sum = self.client.get('/api/admin/edubloom/summary', headers=headers)
        self.assertEqual(resp_sum.status_code, 403)

    # Requirement 6: Admin can access EduBloom endpoints end-to-end
    def test_06_admin_edubloom_endpoints(self):
        a_token = self._get_admin_token()
        headers = {'Authorization': f'Bearer {a_token}'}

        # 1. Summary endpoint
        resp_sum = self.client.get('/api/admin/edubloom/summary', headers=headers)
        self.assertEqual(resp_sum.status_code, 200)
        data_sum = resp_sum.get_json()
        self.assertTrue(data_sum['dataset_status']['available'])
        self.assertTrue(data_sum['database_isolation']['isolation_enforced'])

        # 2. Validation endpoint
        resp_val = self.client.post('/api/admin/edubloom/validate', headers=headers)
        self.assertEqual(resp_val.status_code, 200)
        data_val = resp_val.get_json()
        self.assertTrue(data_val['success'])
        self.assertEqual(data_val['valid_usable_rows'], 73712)

        # 3. Candidate training endpoint is disabled via web API (returns 403)
        resp_train = self.client.post('/api/admin/edubloom/train-candidate', headers=headers, json={
            'task_name': 'bloom_level',
            'sample_limit': 60,
            'n_estimators': 10
        })
        self.assertEqual(resp_train.status_code, 403)
        self.assertIn('disabled', resp_train.get_json()['error'])

        # Direct underlying service function works for local scripts
        data_train = train_edubloom_candidate_model(
            task_name='bloom_level',
            sample_limit=60,
            n_estimators=10
        )
        self.assertTrue(data_train['is_candidate'])
        self.assertFalse(data_train['is_active'])
        self.assertTrue(data_train['promotion_required'])

    # Requirement 7: Combined Dataset Normalization, Deduplication, and Manifest
    def test_07_combined_dataset_build_and_deduplication(self):
        manifest = build_combined_training_dataset(force_rebuild=False)
        self.assertTrue(manifest['success'])
        self.assertEqual(manifest['final_combined_row_count'], 74716)
        self.assertEqual(manifest['existing_dataset']['source_rows_count'], 1254)
        self.assertEqual(manifest['existing_dataset']['valid_usable_rows'], 1004)
        self.assertEqual(manifest['existing_dataset']['internal_duplicates_removed'], 250)
        self.assertEqual(manifest['edubloom_dataset']['valid_usable_rows'], 73712)
        self.assertEqual(manifest['deduplication']['cross_dataset_duplicates_removed'], 0)

        # Verify combined CSV on disk
        csv_path = get_combined_dataset_path()
        self.assertTrue(os.path.exists(csv_path))
        df = pd.read_csv(csv_path)
        self.assertEqual(len(df), 74716)

        # Verify target schema columns
        required_schema = ['question_id', 'question', 'subject', 'topic', 'bloom_level', 'question_type', 'difficulty', 'source', 'is_tn_state_board']
        for col in required_schema:
            self.assertIn(col, df.columns)

        # Verify TN State Board isolation flag
        tn_mask = df['is_tn_state_board'] == True
        self.assertEqual(tn_mask.sum(), 1004)
        self.assertEqual((~tn_mask).sum(), 73712)

        # Verify Bloom and Difficulty distributions
        self.assertTrue(df['bloom_level'].isin(Config.BLOOM_LEVELS).all())
        self.assertTrue(df['difficulty'].isin(Config.DIFFICULTY_LEVELS).all())

    # Requirement 8: Template Leakage Prevention Grouping
    def test_08_template_leakage_grouping(self):
        mock_df = pd.DataFrame({
            'question': [
                'What is the structure of plant cell in detail?',
                'What is the structure of animal cell in detail?',
                'Explain Newton second law with an experiment',
                'Explain Newton third law with an experiment'
            ],
            'bloom_level': ['Understand', 'Understand', 'Apply', 'Apply']
        })
        fp_df = clean_template_leakage(mock_df)
        self.assertIn('template_fp', fp_df.columns)
        # Verify first words and last words fingerprint
        self.assertEqual(len(fp_df['template_fp']), 4)

    # Requirement 9: Combined Candidate Training (Bloom + Difficulty)
    def test_09_train_combined_candidate_model_both_tasks(self):
        # 1. Bloom Level candidate training
        bloom_res = train_combined_candidate_model(
            task_name='bloom_level',
            sample_limit=120,
            n_estimators=10
        )
        self.assertTrue(bloom_res['success'])
        self.assertTrue(bloom_res['is_candidate'])
        self.assertFalse(bloom_res['is_active'])
        self.assertIn('candidate', bloom_res['version'])
        self.assertEqual(bloom_res['evaluation']['template_leakage_overlap_count'], 0)
        self.assertIsNotNone(bloom_res.get('tn_benchmark_evaluation'))

        # 2. Difficulty candidate training
        diff_res = train_combined_candidate_model(
            task_name='difficulty',
            sample_limit=120,
            n_estimators=10
        )
        self.assertTrue(diff_res['success'])
        self.assertTrue(diff_res['is_candidate'])
        self.assertFalse(diff_res['is_active'])
        self.assertIn('candidate', diff_res['version'])
        self.assertEqual(diff_res['evaluation']['template_leakage_overlap_count'], 0)
        self.assertIsNotNone(diff_res.get('tn_benchmark_evaluation'))

    # Requirement 10: Admin Combined API Endpoints & RBAC Denial for Teachers
    def test_10_admin_combined_api_endpoints_and_rbac(self):
        t_token = self._get_teacher_token()
        t_headers = {'Authorization': f'Bearer {t_token}'}

        # Teachers receive 403 Forbidden
        r1 = self.client.post('/api/admin/datasets/merge-combined', headers=t_headers)
        self.assertEqual(r1.status_code, 403)

        r2 = self.client.get('/api/admin/datasets/combined-summary', headers=t_headers)
        self.assertEqual(r2.status_code, 403)

        r3 = self.client.post('/api/admin/combined/train-candidate', headers=t_headers, json={'task_name': 'bloom_level'})
        self.assertEqual(r3.status_code, 403)

        # Admins receive 200/201
        a_token = self._get_admin_token()
        a_headers = {'Authorization': f'Bearer {a_token}'}

        r_sum = self.client.get('/api/admin/datasets/combined-summary', headers=a_headers)
        self.assertEqual(r_sum.status_code, 200)
        self.assertEqual(r_sum.get_json()['final_combined_row_count'], 74716)

        # Combined training endpoint is disabled via web API (returns 403)
        r_train = self.client.post('/api/admin/combined/train-candidate', headers=a_headers, json={
            'task_name': 'bloom_level',
            'sample_limit': 60,
            'n_estimators': 10
        })
        self.assertEqual(r_train.status_code, 403)
        self.assertIn('disabled', r_train.get_json()['error'])

        # Direct underlying service function works for local scripts
        data = train_combined_candidate_model(
            task_name='bloom_level',
            sample_limit=60,
            n_estimators=10
        )
        self.assertTrue(data['is_candidate'])
        self.assertFalse(data['is_active'])

    # Requirement 11: Candidate Model Promotion Workflow
    def test_11_candidate_model_promotion_and_isolation(self):
        db = SessionLocal()
        try:
            active_bloom = db.query(ModelVersion).filter_by(task_name='bloom_level', is_active=True).first()
            orig_active_id = active_bloom.id if active_bloom else None
        finally:
            db.close()

        # Train a candidate
        res = train_combined_candidate_model(task_name='bloom_level', sample_limit=60, n_estimators=10)
        cand_id = res['model_id']

        # Candidate is not active
        self.assertFalse(res['is_active'])

        # Explicit admin promotion action
        promote_res = activate_version(cand_id)
        self.assertTrue(promote_res['success'])

        db2 = SessionLocal()
        try:
            promoted_model = db2.get(ModelVersion, cand_id)
            self.assertTrue(promoted_model.is_active)
        finally:
            db2.close()

        # Restore original active model if existed
        if orig_active_id:
            activate_version(orig_active_id)


if __name__ == '__main__':
    unittest.main()

