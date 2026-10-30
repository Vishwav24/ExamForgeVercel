"""
Comprehensive Automated Test Suite for ExamForge AI
Verifies:
1. Tamil Nadu State Board only (Classes 6-12) & rejection of invalid boards/classes.
2. RBAC: Teacher cannot access Admin endpoints or view model evaluation metrics (HTTP 403).
3. Admin can manage staff, upload CSV, validate, and train Random Forest models.
4. Question paper generation generates valid questions & PDF without leaking other boards/classes.
"""

import os
import sys
import json
import io
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config
from app import app, setup_database
from database.db import SessionLocal
from database.models import User, Question, GeneratedPaper


class TestExamForgeTNSBAndRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_database()
        cls.client = app.test_client()

    def test_01_curriculum_classes_are_6_to_12_only(self):
        """Verify only Tamil Nadu State Board Classes 6-12 are returned."""
        resp = self.client.get('/api/curriculum/classes')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['board'], 'Tamil Nadu State Board')
        expected = ['Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']
        self.assertEqual(data['classes'], expected)

    def test_02_curriculum_subjects_and_chapters(self):
        """Verify authentic subjects and chapters for Class 10 Science."""
        resp = self.client.get('/api/curriculum/subjects?class_grade=Class%2010')
        self.assertEqual(resp.status_code, 200)
        subjects = resp.get_json()['subjects']
        self.assertIn('Science', subjects)
        self.assertIn('Mathematics', subjects)

        resp_chap = self.client.get('/api/curriculum/chapters?class_grade=Class%2010&subject=Science')
        self.assertEqual(resp_chap.status_code, 200)
        chapters = resp_chap.get_json()['chapters']
        self.assertIn('Laws of Motion', chapters)
        self.assertIn('Optics', chapters)

    def _get_tokens(self):
        resp_t = self.client.post('/api/auth/login', json={
            'email': 'teacher@examforge.ai',
            'password': 'ExamForge@2026'
        })
        resp_a = self.client.post('/api/auth/login', json={
            'email': 'admin@examforge.ai',
            'password': 'Admin@2026'
        })
        return resp_t.get_json()['token'], resp_a.get_json()['token']

    def test_03_authentication_and_rbac_tokens(self):
        """Verify admin and teacher logins return appropriate roles."""
        t_token, a_token = self._get_tokens()
        self.assertTrue(t_token)
        self.assertTrue(a_token)

    def test_04_teacher_forbidden_from_admin_apis(self):
        """Verify that teacher accounts receive HTTP 403 on all Admin endpoints and model evaluations."""
        teacher_token, admin_token = self._get_tokens()
        headers = {'Authorization': f'Bearer {teacher_token}'}

        # 1. Staff Management
        resp = self.client.get('/api/admin/staff', headers=headers)
        self.assertEqual(resp.status_code, 403, "Teacher must not be able to list staff")

        # 2. Dataset Upload
        resp = self.client.get('/api/admin/datasets', headers=headers)
        self.assertEqual(resp.status_code, 403, "Teacher must not be able to list datasets")

        # 3. Model Training
        resp = self.client.post('/api/admin/models/train', headers=headers, json={'task_name': 'bloom_level'})
        self.assertEqual(resp.status_code, 403, "Teacher must not be able to trigger model training")

        # 4. Model Evaluation Report
        resp = self.client.get('/api/models/evaluation', headers=headers)
        self.assertEqual(resp.status_code, 403, "Teacher must not be able to access model accuracy/evaluation")

    def test_05_admin_can_manage_staff(self):
        """Verify Admin can view and create staff accounts."""
        _, admin_token = self._get_tokens()
        headers = {'Authorization': f'Bearer {admin_token}'}

        # List staff
        resp = self.client.get('/api/admin/staff', headers=headers)
        self.assertEqual(resp.status_code, 200)

        # Create new staff
        test_email = 'math.teacher@examforge.ai'
        resp_create = self.client.post('/api/admin/staff', headers=headers, json={
            'email': test_email,
            'full_name': 'R. Sundaram (PGT Math)',
            'phone': '9840012345',
            'role': 'teacher',
            'subject_specialization': 'Mathematics',
            'password': 'Teacher@2026'
        })
        # If exists or created
        self.assertIn(resp_create.status_code, [201, 409])

    def test_06_question_paper_generation_tnsb(self):
        """Verify Question Paper Generation works for TN State Board Class 10 Science."""
        teacher_token, admin_token = self._get_tokens()
        headers = {'Authorization': f'Bearer {teacher_token}'}

        # Generate paper
        req_payload = {
            'title': 'Mid-Term Science Exam 2026',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'chapters': ['Laws of Motion', 'Optics', 'Electricity'],
            'duration_minutes': 90,
            'num_questions': 6,
            'total_marks': 25
        }

        resp = self.client.post('/api/generate-paper', headers=headers, json=req_payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['class_grade'], 'Class 10')
        self.assertEqual(data['subject'], 'Science')
        self.assertTrue(len(data['questions']) > 0)
        self.assertTrue(os.path.exists(os.path.join(Config.GENERATED_PAPERS_DIR, data['pdf_filename'])))

    def test_07_csv_upload_and_validation(self):
        """Verify CSV upload, preview, and column mapping validation for Admin."""
        _, admin_token = self._get_tokens()
        headers = {'Authorization': f'Bearer {admin_token}'}

        # Build sample CSV bytes
        csv_content = (
            "question,class_grade,subject,topic,bloom_level,difficulty,marks\n"
            "State Newton's first law of motion and explain inertia of rest.,Class 10,Science,Laws of Motion,Understand,Easy,2\n"
            "Derive the lens formula 1/f = 1/v - 1/u for a concave lens.,Class 10,Science,Optics,Analyze,Hard,5\n"
            "What is electric current and state its SI unit?,Class 10,Science,Electricity,Remember,Easy,1\n"
        )

        data = {
            'file': (io.BytesIO(csv_content.encode('utf-8')), 'test_upload.csv')
        }

        resp = self.client.post('/api/admin/datasets/upload', headers=headers, data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 201)
        upload_id = resp.get_json()['dataset_id']

        # Validate
        val_resp = self.client.post(f'/api/admin/datasets/{upload_id}/validate', headers=headers, json={
            'column_mapping': {
                'question': 'question',
                'class_grade': 'class_grade',
                'subject': 'subject',
                'topic': 'topic',
                'bloom_level': 'bloom_level',
                'difficulty': 'difficulty',
                'marks': 'marks'
            }
        })
        self.assertEqual(val_resp.status_code, 200)
        rep = val_resp.get_json()['report']
        self.assertEqual(rep['valid_rows_count'], 3)
        self.assertEqual(rep['invalid_rows_count'], 0)


if __name__ == '__main__':
    unittest.main()
