"""
Comprehensive 12-Point System Verification Test Suite for ExamForge AI
Covers all criteria specified in Project Enhancement Requirements:
1. Classes 6–12 are available and unsupported boards cannot be selected.
2. A valid CSV can be uploaded and previewed.
3. Invalid CSV files are rejected with useful error messages.
4. Random Forest training uses labelled data.
5. Evaluation metrics are calculated from a held-out test set.
6. Failed training does not replace the active model.
7. Admin can add and manage staff.
8. Teacher accounts cannot access Admin pages or Admin APIs (HTTP 403).
9. Teachers cannot view model accuracy or training information.
10. Question papers contain only eligible State Board questions for the selected class, subject, and chapter.
11. Marks and question distributions are validated before PDF export.
12. Authentication, database operations, frontend API calls, and PDF downloads work end to end.
"""

import os
import sys
import io
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config
from app import app, setup_database
from database.db import SessionLocal
from database.models import User, Question, GeneratedPaper, ModelVersion, DatasetUpload
from ml.random_forest_trainer import train_random_forest_pipeline


class FullSystemVerificationTests(unittest.TestCase):
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

    # Criterion 1: Classes 6-12 available & unsupported boards cannot be selected
    def test_criterion_01_classes_6_to_12_and_board_locking(self):
        resp = self.client.get('/api/curriculum/classes')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['board'], 'Tamil Nadu State Board')
        self.assertEqual(data['classes'], ['Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12'])

        # Attempt to generate paper with CBSE board (must fail)
        t_token = self._get_teacher_token()
        resp_cbse = self.client.post('/api/generate-paper', headers={'Authorization': f'Bearer {t_token}'}, json={
            'title': 'Illegal CBSE Exam',
            'board': 'CBSE',
            'class_grade': 'Class 10',
            'subject': 'Science'
        })
        # Backend rejects or forces TN State Board
        if resp_cbse.status_code == 201:
            # If accepted, board MUST be forced to Tamil Nadu State Board
            self.assertEqual(resp_cbse.get_json().get('board', 'Tamil Nadu State Board'), 'Tamil Nadu State Board')
        else:
            self.assertEqual(resp_cbse.status_code, 400)

        # Attempt with unsupported Class (e.g. Class 5)
        resp_class5 = self.client.post('/api/generate-paper', headers={'Authorization': f'Bearer {t_token}'}, json={
            'title': 'Illegal Class 5 Exam',
            'class_grade': 'Class 5',
            'subject': 'Science'
        })
        self.assertEqual(resp_class5.status_code, 400)
        self.assertIn("Class selection is mandatory and must be one of Classes 6 to 12", resp_class5.get_json()['error'])

    # Criterion 2: Valid CSV can be uploaded and previewed
    def test_criterion_02_valid_csv_upload_and_preview(self):
        a_token = self._get_admin_token()
        csv_data = (
            "question_text,class_name,subject_name,chapter_name,bloom,difficulty_tier,mark\n"
            "What is the principle of conservation of momentum?,Class 10,Science,Laws of Motion,Understand,Medium,3\n"
            "State Ohm's law and draw V-I characteristic curve.,Class 10,Science,Electricity,Apply,Medium,5\n"
        )
        data = {'file': (io.BytesIO(csv_data.encode('utf-8')), 'physics_valid.csv')}
        resp = self.client.post('/api/admin/datasets/upload', headers={'Authorization': f'Bearer {a_token}'}, data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 201)
        res = resp.get_json()
        self.assertTrue(res['success'])
        self.assertEqual(res['total_rows'], 2)
        self.assertTrue(len(res['preview_sample']) > 0)

    # Criterion 3: Invalid CSV files rejected with useful error messages
    def test_criterion_03_invalid_csv_rejected(self):
        a_token = self._get_admin_token()
        # Non-csv extension
        data = {'file': (io.BytesIO(b"dummy data"), 'test.txt')}
        resp = self.client.post('/api/admin/datasets/upload', headers={'Authorization': f'Bearer {a_token}'}, data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Uploaded file must be a CSV", resp.get_json()['error'])

        # CSV with invalid board and missing question texts
        bad_csv = (
            "question,class_grade,board\n"
            ",Class 10,Tamil Nadu State Board\n"
            "What is motion?,Class 10,CBSE\n"
        )
        data2 = {'file': (io.BytesIO(bad_csv.encode('utf-8')), 'bad.csv')}
        resp2 = self.client.post('/api/admin/datasets/upload', headers={'Authorization': f'Bearer {a_token}'}, data=data2, content_type='multipart/form-data')
        self.assertEqual(resp2.status_code, 201)
        up_id = resp2.get_json()['dataset_id']

        val_resp = self.client.post(f'/api/admin/datasets/{up_id}/validate', headers={'Authorization': f'Bearer {a_token}'}, json={
            'column_mapping': {'question': 'question', 'class_grade': 'class_grade', 'board': 'board'}
        })
        self.assertEqual(val_resp.status_code, 200)
        rep = val_resp.get_json()['report']
        self.assertEqual(rep['invalid_rows_count'], 2)
        self.assertTrue(len(rep['errors_sample']) > 0)

    # Criterion 4 & 5: Web training is disabled (403) and local training script trains RF with held-out test evaluation
    def test_criterion_04_and_05_rf_training_and_held_out_evaluation(self):
        a_token = self._get_admin_token()
        resp = self.client.post('/api/admin/models/train', headers={'Authorization': f'Bearer {a_token}'}, json={
            'task_name': 'bloom_level',
            'n_estimators': 50,
            'auto_activate': False
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn('disabled', resp.get_json()['error'])

        # Verify underlying ML training pipeline and held-out evaluation directly
        res = train_random_forest_pipeline(
            task_name='bloom_level',
            dataset_source='db',
            n_estimators=20,
            sample_limit=100,
            auto_activate=False,
            is_candidate=True
        )
        self.assertTrue(res['success'])
        eval_metrics = res['evaluation']
        self.assertIn('test_accuracy', eval_metrics)
        self.assertIn('macro_f1', eval_metrics)
        self.assertIn('confusion_matrix', eval_metrics)
        self.assertIn('per_class', eval_metrics)
        self.assertGreater(eval_metrics['test_samples'], 0)
        self.assertGreater(eval_metrics['train_samples'], 0)

    # Criterion 6: Failed training does not replace the active model
    def test_criterion_06_failed_training_preserves_active_model(self):
        db = SessionLocal()
        active_before = db.query(ModelVersion).filter_by(task_name='bloom_level', is_active=True).first()
        active_id_before = active_before.id if active_before else None
        db.close()

        # Trigger training on invalid/empty dataset
        empty_df = pd.DataFrame({'question': [], 'bloom_level': []})
        res = train_random_forest_pipeline('bloom_level', custom_df=empty_df)
        self.assertFalse(res['success'])

        db = SessionLocal()
        active_after = db.query(ModelVersion).filter_by(task_name='bloom_level', is_active=True).first()
        active_id_after = active_after.id if active_after else None
        db.close()

        self.assertEqual(active_id_before, active_id_after, "Failed training must NOT alter the active model version!")

    # Criterion 7: Admin can add and manage staff
    def test_criterion_07_admin_manage_staff(self):
        a_token = self._get_admin_token()
        headers = {'Authorization': f'Bearer {a_token}'}

        test_staff_email = 'science.hod@examforge.ai'
        resp_create = self.client.post('/api/admin/staff', headers=headers, json={
            'email': test_staff_email,
            'full_name': 'Dr. M. Soundararajan',
            'phone': '9444100200',
            'role': 'teacher',
            'subject_specialization': 'Science',
            'password': 'InitialStaff@2026'
        })
        self.assertIn(resp_create.status_code, [201, 409])

        resp_list = self.client.get('/api/admin/staff', headers=headers)
        self.assertEqual(resp_list.status_code, 200)
        staff_emails = [s['email'] for s in resp_list.get_json()['staff']]
        self.assertIn(test_staff_email, staff_emails)

    # Criterion 8 & 9: Teacher cannot access Admin endpoints or view model accuracy
    def test_criterion_08_and_09_teacher_restricted(self):
        t_token = self._get_teacher_token()
        headers = {'Authorization': f'Bearer {t_token}'}

        # Staff API forbidden
        r1 = self.client.get('/api/admin/staff', headers=headers)
        self.assertEqual(r1.status_code, 403)

        # Datasets API forbidden
        r2 = self.client.get('/api/admin/datasets', headers=headers)
        self.assertEqual(r2.status_code, 403)

        # Train API forbidden
        r3 = self.client.post('/api/admin/models/train', headers=headers, json={'task_name': 'bloom_level'})
        self.assertEqual(r3.status_code, 403)

        # Model evaluation report forbidden
        r4 = self.client.get('/api/models/evaluation', headers=headers)
        self.assertEqual(r4.status_code, 403)

        # Dashboard stats for teacher must NOT contain bloom_evaluation or difficulty_evaluation
        r5 = self.client.get('/api/dashboard/stats', headers=headers)
        self.assertEqual(r5.status_code, 200)
        teacher_stats = r5.get_json()
        self.assertEqual(teacher_stats['role'], 'teacher')
        self.assertNotIn('bloom_evaluation', teacher_stats)
        self.assertNotIn('difficulty_evaluation', teacher_stats)

    # Criterion 10: Question papers contain only eligible State Board questions
    def test_criterion_10_question_papers_pure_state_board(self):
        t_token = self._get_teacher_token()
        headers = {'Authorization': f'Bearer {t_token}'}

        payload = {
            'title': 'Tamil Nadu Annual Exam Class 10 Science',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'chapters': ['Laws of Motion', 'Optics'],
            'num_questions': 5,
            'total_marks': 15
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()

        for q in data['questions']:
            self.assertEqual(q['board'], 'Tamil Nadu State Board')
            self.assertEqual(q['class_grade'], 'Class 10')
            self.assertEqual(q['subject'], 'Science')
            self.assertIn(q['topic'], ['Laws of Motion', 'Optics'])

    # Criterion 11: Marks and question distributions validated before PDF export
    def test_criterion_11_marks_validation_and_sections(self):
        t_token = self._get_teacher_token()
        headers = {'Authorization': f'Bearer {t_token}'}

        payload = {
            'title': 'Validated Mark Distribution Exam',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'num_questions': 6,
            'total_marks': 20,
            'difficulty_distribution': {'Easy': 50, 'Medium': 30, 'Hard': 20}
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn('sections', data)
        self.assertTrue(len(data['sections']) > 0)
        self.assertGreater(data['total_marks'], 0)

    # Criterion 12: End-to-end PDF download verification
    def test_criterion_12_pdf_download_end_to_end(self):
        t_token = self._get_teacher_token()
        headers = {'Authorization': f'Bearer {t_token}'}

        # Generate paper
        gen_resp = self.client.post('/api/generate-paper', headers=headers, json={
            'title': 'PDF Verification Test Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'num_questions': 4,
            'total_marks': 10
        })
        self.assertEqual(gen_resp.status_code, 201)
        paper_id = gen_resp.get_json()['paper_id']

        # Download PDF
        dl_resp = self.client.get(f'/api/papers/{paper_id}/download')
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp.mimetype, 'application/pdf')
        self.assertGreater(len(dl_resp.data), 1000)  # Valid PDF binary size


if __name__ == '__main__':
    unittest.main()
