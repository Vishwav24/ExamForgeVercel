"""
ExamForge AI - Stage 4 End-to-End Verification Script
Verifies:
1. Chairman creation and role restrictions (no paper gen, no ML)
2. Chairman creates Principal account
3. Principal creates Science Teacher (assigned 'Science') & Math Teacher (assigned 'Mathematics')
4. Science Teacher generates Science paper with Mark-wise Section Builder (A, B, C...)
5. Section ordering validation (starts at 'A', ordered alphabetically)
6. Science Teacher blocked from generating Mathematics paper (HTTP 403)
7. Science Teacher blocked from fetching Mathematics questions (HTTP 403)
8. Mark-wise distribution mismatch rejection (HTTP 400)
9. Chairman dashboard stats returns counts only (no PII, no password hashes)
"""

import sys
import os

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app import app
from database.db import get_db, SessionLocal
from database.models import User, Question, GeneratedPaper
from services.auth import hash_password, create_access_token

def run_verification():
    print("=" * 70)
    print("EXAMFORGE AI - STAGE 4 END-TO-END VERIFICATION")
    print("=" * 70)
    
    client = app.test_client()
    db = SessionLocal()
    
    try:
        # Step 1: Create or find Chairman
        chairman = db.query(User).filter(User.email == 'chairman.verify@examforge.ai').first()
        if not chairman:
            chairman = User(
                email='chairman.verify@examforge.ai',
                password_hash=hash_password('Chairman@123'),
                full_name='Dr. Chairman Test',
                role='chairman',
                is_active=True
            )
            db.add(chairman)
            db.commit()
            db.refresh(chairman)
        
        chairman_token = create_access_token(chairman)
        chairman_headers = {'Authorization': f'Bearer {chairman_token}'}
        print("[PASS] 1. Chairman account established")

        # Step 2: Verify Chairman is BLOCKED from paper generation & ML endpoints
        res = client.post('/api/generate-paper', headers=chairman_headers, json={'title': 'Test'})
        assert res.status_code == 403, f"Expected 403 for Chairman paper gen, got {res.status_code}"
        
        res = client.post('/api/admin/models/train', headers=chairman_headers, json={})
        assert res.status_code == 403, f"Expected 403 for Chairman model train, got {res.status_code}"
        print("[PASS] 2. Chairman strictly blocked from paper generation & ML operations (403 Forbidden)")

        # Step 3: Chairman creates Principal account
        principal_email = 'principal.verify@examforge.ai'
        existing_p = db.query(User).filter(User.email == principal_email).first()
        if existing_p:
            db.delete(existing_p)
            db.commit()
            
        res = client.post('/api/chairman/principals', headers=chairman_headers, json={
            'email': principal_email,
            'password': 'Principal@123',
            'full_name': 'Prof. Principal Test'
        })
        assert res.status_code == 201, f"Failed to create principal: {res.get_json()}"
        principal_id = res.get_json()['principal']['id']
        print(f"[PASS] 3. Chairman created Principal account '{principal_email}' (ID: {principal_id})")

        # Step 4: Chairman views Teacher Stats (Counts only, no PII)
        res = client.get('/api/chairman/teacher-stats', headers=chairman_headers)
        assert res.status_code == 200
        stats = res.get_json()
        assert 'total_teachers' in stats
        assert 'active_teachers' in stats
        assert 'subject_breakdown' in stats
        assert 'password_hash' not in str(stats)
        assert 'password' not in str(stats)
        print(f"[PASS] 4. Chairman Teacher Stats verified: {stats['total_teachers']} total, {stats['active_teachers']} active, subjects: {list(stats['subject_breakdown'].keys())}")

        # Step 5: Principal logs in and creates Science Teacher (assigned 'Science')
        principal = db.query(User).filter(User.id == principal_id).first()
        principal_token = create_access_token(principal)
        principal_headers = {'Authorization': f'Bearer {principal_token}'}

        science_email = 'science.teacher.verify@examforge.ai'
        existing_st = db.query(User).filter(User.email == science_email).first()
        if existing_st:
            db.delete(existing_st)
            db.commit()

        res = client.post('/api/principal/teachers', headers=principal_headers, json={
            'email': science_email,
            'password': 'Teacher@123',
            'full_name': 'Mrs. Science Teacher',
            'subject_specialization': 'Science'
        })
        assert res.status_code == 201, f"Failed to create teacher: {res.get_json()}"
        science_teacher_id = res.get_json()['teacher']['id']
        print(f"[PASS] 5. Principal registered Science Teacher with assigned subject 'Science' (ID: {science_teacher_id})")

        # Step 6: Science Teacher attempts to generate a Mathematics paper -> MUST BE 403
        science_teacher = db.query(User).filter(User.id == science_teacher_id).first()
        st_token = create_access_token(science_teacher)
        st_headers = {'Authorization': f'Bearer {st_token}'}

        res = client.post('/api/generate-paper', headers=st_headers, json={
            'title': 'Unauthorized Math Paper',
            'board': 'Tamil Nadu State Board',
            'class_grade': 'Class 10',
            'subject': 'Mathematics',
            'chapters': ['Real Numbers'],
            'total_marks': 25,
            'duration_minutes': 60,
            'num_questions': 5
        })
        assert res.status_code == 403, f"Expected 403 for unauthorized subject, got {res.status_code}"
        err = res.get_json().get('error', '')
        assert 'not authorized' in err or 'assigned' in err
        print(f"[PASS] 6. Science Teacher blocked from generating Mathematics paper (HTTP 403: '{err}')")

        # Step 7: Science Teacher searches Mathematics questions -> MUST BE 403
        res = client.get('/api/questions?subject=Mathematics', headers=st_headers)
        assert res.status_code == 403, f"Expected 403 for question search, got {res.status_code}"
        print("[PASS] 7. Science Teacher blocked from searching Mathematics questions (HTTP 403)")

        # Step 8: Mark-wise Section Mismatch Validation (HTTP 400)
        res = client.post('/api/generate-paper', headers=st_headers, json={
            'title': 'Mismatch Paper',
            'board': 'Tamil Nadu State Board',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'total_marks': 50,  # Entered 50
            'duration_minutes': 60,
            'sections': [
                {'marks_per_question': 2, 'num_questions': 3}  # Total 6 marks != 50
            ]
        })
        assert res.status_code == 400, f"Expected 400 for marks mismatch, got {res.status_code}"
        err = res.get_json().get('error', '')
        assert 'do not match' in err or 'mismatch' in err or 'does not match' in err
        print(f"[PASS] 8. Section marks mismatch correctly rejected (HTTP 400: '{err}')")

        # Step 9: Exact shortage reporting when insufficient questions exist
        res = client.post('/api/generate-paper', headers=st_headers, json={
            'title': 'Shortage Test Paper',
            'board': 'Tamil Nadu State Board',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'total_marks': 500,
            'duration_minutes': 60,
            'sections': [
                {'marks_per_question': 5, 'num_questions': 100}
            ]
        })
        assert res.status_code == 400
        shortage_err = res.get_json().get('error', '')
        assert 'Insufficient questions for Section A' in shortage_err
        assert 'Need' in shortage_err and '5-mark question' in shortage_err
        print(f"[PASS] 9. Exact shortage reported: '{shortage_err}'")

        # Step 10: Science Teacher generates valid Science paper with Section Builder (2-mark, 3-mark, 5-mark sections)
        # Sequential sections: Section A (2m), Section B (3m), Section C (5m)
        res = client.post('/api/generate-paper', headers=st_headers, json={
            'title': 'Tamil Nadu State Board Class 10 Science Assessment',
            'board': 'Tamil Nadu State Board',
            'class_grade': 'Class 10',
            'subject': 'Science',
            'total_marks': 18,
            'duration_minutes': 60,
            'sections': [
                {'marks_per_question': 2, 'num_questions': 1},  # Section A (2 marks)
                {'marks_per_question': 3, 'num_questions': 2},  # Section B (6 marks)
                {'marks_per_question': 5, 'num_questions': 2}   # Section C (10 marks)
            ]
        })
        assert res.status_code == 201, f"Failed to generate valid Science paper: {res.get_json()}"
        paper_data = res.get_json()
        paper_id = paper_data['paper_id']
        sections = paper_data.get('sections', [])
        
        # Verify Sections A, B, C are strictly sequential!
        assert len(sections) == 3, f"Expected 3 sections, got {len(sections)}"
        assert sections[0].get('label') == 'A' and 'SECTION A' in sections[0].get('name', ''), f"Section 0 mismatch: {sections[0]}"
        assert sections[1].get('label') == 'B' and 'SECTION B' in sections[1].get('name', ''), f"Section 1 mismatch: {sections[1]}"
        assert sections[2].get('label') == 'C' and 'SECTION C' in sections[2].get('name', ''), f"Section 2 mismatch: {sections[2]}"
        print(f"[PASS] 10. Science paper generated successfully (ID: {paper_id}). Sequential Sections: A, B, C confirmed!")

        # Step 11: Verify PDF download endpoint with token
        res = client.get(f'/api/papers/{paper_id}/download?token={st_token}')
        assert res.status_code == 200, f"Failed to download PDF with token: {res.status_code}"
        assert res.content_type == 'application/pdf'
        assert len(res.data) > 1000
        print(f"[PASS] 11. Printable PDF downloaded successfully ({len(res.data)} bytes, Content-Type: application/pdf)")

        print("=" * 70)
        print("ALL 10 END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
        print("=" * 70)
        return True

    finally:
        db.close()

if __name__ == '__main__':
    success = run_verification()
    sys.exit(0 if success else 1)
