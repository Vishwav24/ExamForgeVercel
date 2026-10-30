"""
Comprehensive Automated Test Suite for:
1. Institutional Role Hierarchy (Chairman -> Principal -> Teacher, Admin)
2. Strict Subject-Based Access Control
3. Section A Ordering Bug Fix
4. Mark-Wise Question Distribution (Dynamic Section Builder) & Exact Shortage Reporting
5. Paper Ownership & PDF Download Authorization
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config
from app import app, setup_database
from database.db import SessionLocal
from database.models import User, Question, GeneratedPaper, AuditLog
from services.auth import hash_password, create_access_token


class TestInstitutionalRolesAndSubjectControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_database()
        cls.client = app.test_client()

        # Create isolated institutional test accounts in DB
        db = SessionLocal()
        try:
            # 1. Chairman
            cls.chairman = db.query(User).filter_by(email='chairman.test@examforge.ai').first()
            if not cls.chairman:
                cls.chairman = User(
                    email='chairman.test@examforge.ai',
                    full_name='Dr. K. Chairman',
                    role='chairman',
                    password_hash=hash_password('Chairman@2026'),
                    is_active=True
                )
                db.add(cls.chairman)

            # 2. Principal
            cls.principal = db.query(User).filter_by(email='principal.test@examforge.ai').first()
            if not cls.principal:
                cls.principal = User(
                    email='principal.test@examforge.ai',
                    full_name='Dr. P. Principal',
                    role='principal',
                    password_hash=hash_password('Principal@2026'),
                    is_active=True
                )
                db.add(cls.principal)

            # 3. Science Teacher (Science only)
            cls.science_teacher = db.query(User).filter_by(email='science.only@examforge.ai').first()
            if not cls.science_teacher:
                cls.science_teacher = User(
                    email='science.only@examforge.ai',
                    full_name='Science Faculty',
                    role='teacher',
                    subject_specialization='Science',
                    password_hash=hash_password('Teacher@2026'),
                    is_active=True
                )
                db.add(cls.science_teacher)

            # 4. Mathematics Teacher (Mathematics only)
            cls.math_teacher = db.query(User).filter_by(email='math.only@examforge.ai').first()
            if not cls.math_teacher:
                cls.math_teacher = User(
                    email='math.only@examforge.ai',
                    full_name='Math Faculty',
                    role='teacher',
                    subject_specialization='Mathematics',
                    password_hash=hash_password('Teacher@2026'),
                    is_active=True
                )
                db.add(cls.math_teacher)

            # 5. Dual Subject Teacher (Science and Mathematics)
            cls.dual_teacher = db.query(User).filter_by(email='dual.subject@examforge.ai').first()
            if not cls.dual_teacher:
                cls.dual_teacher = User(
                    email='dual.subject@examforge.ai',
                    full_name='Dual Faculty',
                    role='teacher',
                    subject_specialization='Science, Mathematics',
                    password_hash=hash_password('Teacher@2026'),
                    is_active=True
                )
                db.add(cls.dual_teacher)

            # 6. Unassigned Teacher (No subjects assigned)
            cls.unassigned_teacher = db.query(User).filter_by(email='unassigned@examforge.ai').first()
            if not cls.unassigned_teacher:
                cls.unassigned_teacher = User(
                    email='unassigned@examforge.ai',
                    full_name='Unassigned Faculty',
                    role='teacher',
                    subject_specialization=None,
                    password_hash=hash_password('Teacher@2026'),
                    is_active=True
                )
                db.add(cls.unassigned_teacher)

            db.commit()

            # Refresh models
            db.refresh(cls.chairman)
            db.refresh(cls.principal)
            db.refresh(cls.science_teacher)
            db.refresh(cls.math_teacher)
            db.refresh(cls.dual_teacher)
            db.refresh(cls.unassigned_teacher)

            cls.chairman_token = create_access_token(cls.chairman)
            cls.principal_token = create_access_token(cls.principal)
            cls.science_token = create_access_token(cls.science_teacher)
            cls.math_token = create_access_token(cls.math_teacher)
            cls.dual_token = create_access_token(cls.dual_teacher)
            cls.unassigned_token = create_access_token(cls.unassigned_teacher)

            # Get admin token
            admin_user = db.query(User).filter_by(role='admin').first()
            cls.admin_token = create_access_token(admin_user)

        finally:
            db.close()

    # =========================================================================
    # 1. CHAIRMAN TESTS
    # =========================================================================

    def test_01_chairman_can_manage_principals(self):
        """Chairman can list, create, edit, and reset password for Principals."""
        headers = {'Authorization': f'Bearer {self.chairman_token}'}

        # 1. List principals
        resp = self.client.get('/api/chairman/principals', headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('principals', data)
        self.assertGreaterEqual(data['total'], 1)

        # 2. Create a new principal
        new_principal_email = 'new.principal.test@examforge.ai'
        resp_create = self.client.post('/api/chairman/principals', headers=headers, json={
            'email': new_principal_email,
            'full_name': 'Prof. M. Principal',
            'phone': '9840099999',
            'password': 'Principal@2026'
        })
        self.assertIn(resp_create.status_code, [201, 409])

        # 3. Update principal
        resp_up = self.client.put(f'/api/chairman/principals/{self.principal.id}', headers=headers, json={
            'full_name': 'Dr. P. Principal (Updated)',
            'is_active': True
        })
        self.assertEqual(resp_up.status_code, 200)

        # 4. Reset principal password
        resp_pw = self.client.post(f'/api/chairman/principals/{self.principal.id}/reset-password', headers=headers, json={
            'password': 'NewPassword@2026'
        })
        self.assertEqual(resp_pw.status_code, 200)

    def test_02_chairman_teacher_stats_counts_only(self):
        """Chairman dashboard returns actual database teacher counts and subject breakdown with zero exposed passwords."""
        headers = {'Authorization': f'Bearer {self.chairman_token}'}
        resp = self.client.get('/api/chairman/teacher-stats', headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn('total_teachers', data)
        self.assertIn('active_teachers', data)
        self.assertIn('inactive_teachers', data)
        self.assertIn('subject_counts', data)
        self.assertIn('unassigned_teachers', data)
        self.assertGreaterEqual(data['total_teachers'], 3)
        self.assertIn('Science', data['subject_counts'])
        self.assertIn('Mathematics', data['subject_counts'])

        # Guarantee zero password or hash exposure
        raw_str = json.dumps(data)
        self.assertNotIn('password', raw_str.lower())
        self.assertNotIn('pbkdf2', raw_str.lower())

    def test_03_chairman_forbidden_from_unauthorized_operations(self):
        """Chairman must NOT generate question papers, upload datasets, or train models."""
        headers = {'Authorization': f'Bearer {self.chairman_token}'}

        # 1. Paper Generation
        resp_gen = self.client.post('/api/generate-paper', headers=headers, json={
            'title': 'Illegal Paper',
            'class_grade': 'Class 10',
            'subject': 'Science'
        })
        self.assertEqual(resp_gen.status_code, 403, "Chairman must not be able to generate papers")

        # 2. Paper Preview
        resp_prev = self.client.post('/api/generate-paper/preview', headers=headers, json={
            'class_grade': 'Class 10',
            'subject': 'Science'
        })
        self.assertEqual(resp_prev.status_code, 403, "Chairman must not be able to preview paper blueprint")

        # 3. Model Training
        resp_train = self.client.post('/api/admin/models/train', headers=headers, json={'task_name': 'bloom_level'})
        self.assertEqual(resp_train.status_code, 403, "Chairman must not access model training")

        # 4. Model Evaluation
        resp_eval = self.client.get('/api/models/evaluation', headers=headers)
        self.assertEqual(resp_eval.status_code, 403, "Chairman must not access model evaluation")

    # =========================================================================
    # 2. PRINCIPAL TESTS
    # =========================================================================

    def test_04_principal_can_manage_teachers_and_assign_subjects(self):
        """Principal can create, update teacher accounts, and assign single or multiple subjects."""
        headers = {'Authorization': f'Bearer {self.principal_token}'}

        # 1. List teachers
        resp_list = self.client.get('/api/principal/teachers', headers=headers)
        self.assertEqual(resp_list.status_code, 200)
        self.assertGreaterEqual(resp_list.get_json()['total'], 1)

        # 2. Create teacher with assigned subject
        new_teacher_email = 'history.teacher.test@examforge.ai'
        resp_create = self.client.post('/api/principal/teachers', headers=headers, json={
            'email': new_teacher_email,
            'full_name': 'History Specialist',
            'assigned_subjects': ['Social Science'],
            'password': 'Teacher@2026'
        })
        self.assertIn(resp_create.status_code, [201, 409])

        # 3. Update teacher to multi-subject assignment
        resp_up = self.client.put(f'/api/principal/teachers/{self.science_teacher.id}', headers=headers, json={
            'assigned_subjects': ['Science', 'Social Science']
        })
        self.assertEqual(resp_up.status_code, 200)
        t_data = resp_up.get_json()['teacher']
        self.assertIn('Science', t_data['assigned_subjects'])
        self.assertIn('Social Science', t_data['assigned_subjects'])

        # Restore original Science assignment
        self.client.put(f'/api/principal/teachers/{self.science_teacher.id}', headers=headers, json={
            'assigned_subjects': ['Science']
        })

    def test_05_principal_cannot_manage_chairman_or_admin(self):
        """Principal cannot access Chairman principal management or Admin model training."""
        headers = {'Authorization': f'Bearer {self.principal_token}'}

        # Cannot list or create principals
        resp_p = self.client.get('/api/chairman/principals', headers=headers)
        self.assertEqual(resp_p.status_code, 403)

        # Cannot train models
        resp_train = self.client.post('/api/admin/models/train', headers=headers, json={'task_name': 'bloom_level'})
        self.assertEqual(resp_train.status_code, 403)

    # =========================================================================
    # 3. SUBJECT-BASED ACCESS CONTROL TESTS
    # =========================================================================

    def test_06_science_teacher_can_generate_science_paper(self):
        """Science teacher can successfully generate a Science question paper."""
        headers = {'Authorization': f'Bearer {self.science_token}'}
        payload = {
            'title': 'Science Test Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'chapters': ['Laws of Motion', 'Optics'],
            'num_questions': 4,
            'total_marks': 10
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['subject'], 'Science')

    def test_07_science_teacher_forbidden_from_mathematics(self):
        """Science teacher is rejected with HTTP 403 when requesting Mathematics paper."""
        headers = {'Authorization': f'Bearer {self.science_token}'}
        payload = {
            'title': 'Unauthorized Math Paper',
            'class_grade': 'Class 10',
            'subject': 'Mathematics',
            'num_questions': 4,
            'total_marks': 10
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("authorized to generate question papers only for your assigned subject", resp.get_json()['error'])

    def test_08_mathematics_teacher_forbidden_from_science(self):
        """Mathematics teacher is rejected with HTTP 403 when requesting Science paper."""
        headers = {'Authorization': f'Bearer {self.math_token}'}
        payload = {
            'title': 'Unauthorized Science Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'num_questions': 4,
            'total_marks': 10
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("authorized to generate question papers only for your assigned subject", resp.get_json()['error'])

    def test_09_dual_subject_teacher_can_generate_both_subjects_only(self):
        """Teacher assigned Science & Mathematics can generate both, but cannot generate English."""
        headers = {'Authorization': f'Bearer {self.dual_token}'}

        # 1. Science allowed
        resp_sci = self.client.post('/api/generate-paper', headers=headers, json={
            'title': 'Dual Teacher Science Exam',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'num_questions': 4,
            'total_marks': 10
        })
        self.assertEqual(resp_sci.status_code, 201)

        # 2. Mathematics allowed
        resp_math = self.client.post('/api/generate-paper', headers=headers, json={
            'title': 'Dual Teacher Math Exam',
            'class_grade': 'Class 10',
            'subject': 'Mathematics',
            'num_questions': 4,
            'total_marks': 10
        })
        self.assertEqual(resp_math.status_code, 201)

        # 3. English forbidden (HTTP 403)
        resp_eng = self.client.post('/api/generate-paper', headers=headers, json={
            'title': 'Unauthorized English Exam',
            'class_grade': 'Class 10',
            'subject': 'English',
            'num_questions': 4,
            'total_marks': 10
        })
        self.assertEqual(resp_eng.status_code, 403)

    def test_10_unassigned_teacher_cannot_generate_paper(self):
        """Teacher with no assigned subject receives HTTP 403 with clear contact message."""
        headers = {'Authorization': f'Bearer {self.unassigned_token}'}
        resp = self.client.post('/api/generate-paper', headers=headers, json={
            'title': 'Unassigned Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'num_questions': 4,
            'total_marks': 10
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn("No subject assigned. Please contact your Principal.", resp.get_json()['error'])

    def test_11_curriculum_subjects_filtered_for_teachers(self):
        """Subject dropdown endpoint filters subjects strictly based on teacher assignment."""
        # 1. Science teacher gets Science only
        resp_s = self.client.get('/api/curriculum/subjects?class_grade=Class%2010', headers={'Authorization': f'Bearer {self.science_token}'})
        self.assertEqual(resp_s.status_code, 200)
        self.assertEqual(resp_s.get_json()['subjects'], ['Science'])

        # 2. Unassigned teacher gets empty subjects list with clear message
        resp_u = self.client.get('/api/curriculum/subjects?class_grade=Class%2010', headers={'Authorization': f'Bearer {self.unassigned_token}'})
        self.assertEqual(resp_u.status_code, 200)
        u_data = resp_u.get_json()
        self.assertEqual(u_data['subjects'], [])
        self.assertIn("No subject assigned. Please contact your Principal.", u_data.get('message', ''))

    # =========================================================================
    # 4. SECTION A ORDERING & MARK-WISE DISTRIBUTION TESTS
    # =========================================================================

    def test_12_every_paper_starts_with_section_a_even_with_only_5_mark_questions(self):
        """A paper with only 5-mark questions must start with Section A, never Section C."""
        headers = {'Authorization': f'Bearer {self.science_token}'}
        payload = {
            'title': 'Higher Order Section A Test Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'total_marks': 10,
            'sections': [
                {
                    'marks_per_question': 5,
                    'num_questions': 2,
                    'title': 'ESSAY & LONG ANSWER QUESTIONS'
                }
            ]
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        sections = data['sections']
        self.assertGreaterEqual(len(sections), 1)

        # First section MUST be Section A
        first_section = sections[0]
        self.assertEqual(first_section['label'], 'A')
        self.assertTrue(first_section['name'].startswith('SECTION A'))
        self.assertEqual(first_section['marks_per_question'], 5)
        self.assertEqual(first_section['num_questions'], 2)
        self.assertEqual(first_section['total_section_marks'], 10)

    def test_13_dynamic_section_builder_sequential_sections_a_b_c_d(self):
        """Dynamic section builder generates sequential Sections A, B, C with exact totals."""
        headers = {'Authorization': f'Bearer {self.science_token}'}
        payload = {
            'title': 'Terminal Science Comprehensive Exam',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'total_marks': 18,
            'sections': [
                {'marks_per_question': 2, 'num_questions': 1},  # 2 marks
                {'marks_per_question': 3, 'num_questions': 2},  # 6 marks
                {'marks_per_question': 5, 'num_questions': 2},  # 10 marks
            ]
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        sections = data['sections']
        self.assertEqual(len(sections), 3)

        # Verify sequential labels A, B, C
        self.assertEqual(sections[0]['label'], 'A')
        self.assertTrue(sections[0]['name'].startswith('SECTION A'))
        self.assertEqual(sections[1]['label'], 'B')
        self.assertTrue(sections[1]['name'].startswith('SECTION B'))
        self.assertEqual(sections[2]['label'], 'C')
        self.assertTrue(sections[2]['name'].startswith('SECTION C'))

        # Verify continuous sequential question numbering (1 to 5)
        questions = data['questions']
        self.assertEqual(len(questions), 5)
        disp_numbers = [q['display_number'] for q in questions]
        self.assertEqual(disp_numbers, list(range(1, 6)))

    def test_14_mark_mismatch_rejected_with_400(self):
        """Mismatch between entered total marks and calculated section total marks is rejected."""
        headers = {'Authorization': f'Bearer {self.science_token}'}
        payload = {
            'title': 'Mismatch Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'total_marks': 50,  # Expected 50
            'sections': [
                {'marks_per_question': 1, 'num_questions': 5},  # 5
                {'marks_per_question': 2, 'num_questions': 5},  # 10 -> Total is 15 != 50
            ]
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("do not match", resp.get_json()['error'])

    def test_15_exact_shortage_reported_when_insufficient_questions(self):
        """When question bank has insufficient questions for a mark value, report exact shortage."""
        headers = {'Authorization': f'Bearer {self.science_token}'}
        payload = {
            'title': 'Shortage Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'total_marks': 750,
            'sections': [
                {'marks_per_question': 5, 'num_questions': 150}  # 150 5-mark questions unavailable
            ]
        }
        resp = self.client.post('/api/generate-paper', headers=headers, json=payload)
        self.assertEqual(resp.status_code, 400)
        err = resp.get_json()['error']
        self.assertIn("Insufficient questions for Section A", err)
        self.assertIn("Need", err)
        self.assertIn("5-mark question(s)", err)

    # =========================================================================
    # 5. PAPER OWNERSHIP & PDF DOWNLOAD RESTRICTION TESTS
    # =========================================================================

    def test_16_teacher_cannot_access_or_download_other_teachers_paper(self):
        """Teacher A cannot view details or download PDF of paper generated by Teacher B."""
        # 1. Science teacher generates paper
        gen_resp = self.client.post('/api/generate-paper', headers={'Authorization': f'Bearer {self.science_token}'}, json={
            'title': 'Science Teacher Unique Paper',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'num_questions': 4,
            'total_marks': 10
        })
        self.assertEqual(gen_resp.status_code, 201)
        paper_id = gen_resp.get_json()['paper_id']

        # 2. Math teacher attempts to get paper details
        resp_math_get = self.client.get(f'/api/papers/{paper_id}', headers={'Authorization': f'Bearer {self.math_token}'})
        self.assertEqual(resp_math_get.status_code, 403)

        # 3. Math teacher attempts to download PDF
        resp_math_dl = self.client.get(f'/api/papers/{paper_id}/download', headers={'Authorization': f'Bearer {self.math_token}'})
        self.assertEqual(resp_math_dl.status_code, 403)

        # 4. Science teacher (owner) CAN download PDF
        resp_owner_dl = self.client.get(f'/api/papers/{paper_id}/download', headers={'Authorization': f'Bearer {self.science_token}'})
        self.assertEqual(resp_owner_dl.status_code, 200)
        self.assertEqual(resp_owner_dl.mimetype, 'application/pdf')


if __name__ == '__main__':
    unittest.main()
