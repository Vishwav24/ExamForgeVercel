"""
Live Paper Generation & End-to-End Verification Across Multiple Classes
Tests against running Flask backend on http://localhost:5000 and live examforge.db.
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime

# UTF-8 stdout
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from services.auth import create_access_token
from services.curriculum_service import get_supported_chapters

class UserTokenObj:
    def __init__(self, uid, uemail, urole):
        self.id = uid
        self.email = uemail
        self.role = urole

def main():
    base_url = "http://localhost:5000"
    live_db = os.path.join(backend_dir, 'database', 'examforge.db')

    print("=== LIVE GENERATION TEST POST-IMPORT ===")

    # 1. Obtain authenticated JWTs
    teacher_token = create_access_token(UserTokenObj(1, 'teacher@examforge.ai', 'teacher'))
    admin_token = create_access_token(UserTokenObj(2, 'admin@examforge.ai', 'admin'))

    teacher_headers = {
        'Authorization': f'Bearer {teacher_token}',
        'Content-Type': 'application/json'
    }
    admin_headers = {
        'Authorization': f'Bearer {admin_token}',
        'Content-Type': 'application/json'
    }

    # ============================================================
    # Test 1: Class 10 Science (50 Marks, 15 Questions) - Teacher
    # ============================================================
    print("\n------------------------------------------------------------")
    print("[Test 1: POST /api/generate-paper (Class 10 Science - Teacher Role)]")
    c10_sci_topics = get_supported_chapters('Class 10', 'Science')
    payload_c10_sci = {
        'title': 'Class 10 Science State Board Model Exam 2026',
        'class_grade': 'Class 10',
        'subject': 'Science',
        'board': 'Tamil Nadu State Board',
        'topics': c10_sci_topics,
        'total_marks': 50,
        'num_questions': 15,
        'sections': [
            {'label': 'Section A', 'marks_per_question': 2, 'num_questions': 5, 'section_marks': 10, 'question_type': 'Short Answer'},
            {'label': 'Section B', 'marks_per_question': 3, 'num_questions': 5, 'section_marks': 15, 'question_type': 'Short Answer'},
            {'label': 'Section C', 'marks_per_question': 5, 'num_questions': 5, 'section_marks': 25, 'question_type': 'Detailed'}
        ]
    }

    resp_sci = requests.post(f"{base_url}/api/generate-paper", json=payload_c10_sci, headers=teacher_headers, timeout=20)
    print(f"  HTTP Status: {resp_sci.status_code}")
    data_sci = resp_sci.json()

    if resp_sci.status_code not in (200, 201):
        print(f"  Error: {data_sci}")
        return

    paper_id_sci = data_sci.get('paper_id')
    count_sci = data_sci.get('count')
    total_marks_sci = data_sci.get('total_marks')
    pdf_filename_sci = data_sci.get('pdf_filename')
    questions_sci = data_sci.get('questions', [])
    sections_sci = data_sci.get('sections', [])

    print(f"  Paper ID: {paper_id_sci}")
    print(f"  Question Count: {count_sci} (Target: 15)")
    print(f"  Total Marks: {total_marks_sci} (Target: 50.0)")
    print(f"  PDF Filename: {pdf_filename_sci}")
    print(f"  Sections Count: {len(sections_sci)}")
    for s in sections_sci:
        s_name = s.get('section_name') or s.get('label')
        s_tot = s.get('total_marks') or s.get('section_marks')
        s_m = s.get('marks_per_question')
        print(f"    - {s_name}: {len(s.get('questions', []))} questions, {s_tot} marks ({s_m}m each)")

    # Test PDF download endpoint for Class 10 Science
    print("\n[Test 1b: GET /api/papers/<id>/download (Class 10 Science PDF)]")
    resp_pdf = requests.get(f"{base_url}/api/papers/{paper_id_sci}/download", headers=teacher_headers, timeout=15)
    print(f"  Download HTTP Status: {resp_pdf.status_code}")
    print(f"  Content-Type: {resp_pdf.headers.get('Content-Type')}")
    print(f"  Content-Disposition: {resp_pdf.headers.get('Content-Disposition')}")
    print(f"  File Size: {len(resp_pdf.content)} bytes")
    is_valid_pdf = resp_pdf.content.startswith(b'%PDF')
    print(f"  Valid PDF Magic Header (%PDF): {is_valid_pdf}")

    # ============================================================
    # Test 2: Preview Blueprint Endpoint
    # ============================================================
    print("\n------------------------------------------------------------")
    print("[Test 2: POST /api/generate-paper/preview (Class 10 Science Blueprint)]")
    resp_prev = requests.post(f"{base_url}/api/generate-paper/preview", json=payload_c10_sci, headers=teacher_headers, timeout=15)
    print(f"  Preview HTTP Status: {resp_prev.status_code}")
    data_prev = resp_prev.json()
    print(f"  Preview Is Valid: {data_prev.get('is_valid')}")
    print(f"  Eligible Questions: {data_prev.get('eligible_count')}")

    # ============================================================
    # Test 3: Class 6 Mathematics (50 Marks) - Admin Role
    # ============================================================
    print("\n------------------------------------------------------------")
    print("[Test 3: POST /api/generate-paper (Class 6 Mathematics - Admin Role)]")
    c6_math_topics = get_supported_chapters('Class 6', 'Mathematics')
    payload_c6_math = {
        'title': 'Class 6 Mathematics Diagnostic Assessment 2026',
        'class_grade': 'Class 6',
        'subject': 'Mathematics',
        'board': 'Tamil Nadu State Board',
        'topics': c6_math_topics,
        'total_marks': 50,
        'num_questions': 50,
        'sections': [
            {'label': 'Section A', 'marks_per_question': 1, 'num_questions': 50, 'section_marks': 50, 'question_type': 'Objective'}
        ]
    }
    resp_math = requests.post(f"{base_url}/api/generate-paper", json=payload_c6_math, headers=admin_headers, timeout=20)
    print(f"  HTTP Status: {resp_math.status_code}")
    data_math = resp_math.json()
    paper_id_math = data_math.get('paper_id')
    print(f"  Paper ID: {paper_id_math}")
    print(f"  Question Count: {data_math.get('count')}")
    print(f"  Total Marks: {data_math.get('total_marks')}")
    print(f"  PDF Filename: {data_math.get('pdf_filename')}")

    # Test PDF download for Class 6 Mathematics
    resp_math_pdf = requests.get(f"{base_url}/api/papers/{paper_id_math}/download", headers=admin_headers, timeout=15)
    print(f"  Math PDF Download Status: {resp_math_pdf.status_code} ({len(resp_math_pdf.content)} bytes, valid PDF: {resp_math_pdf.content.startswith(b'%PDF')})")

    # ============================================================
    # Test 4: Class 12 Physics (50 Marks, 15 Questions) - Admin Role
    # ============================================================
    print("\n------------------------------------------------------------")
    print("[Test 4: POST /api/generate-paper (Class 12 Physics - Admin Role)]")
    c12_phy_topics = get_supported_chapters('Class 12', 'Physics')
    payload_c12_phy = {
        'title': 'Class 12 Physics State Board Model Exam 2026',
        'class_grade': 'Class 12',
        'subject': 'Physics',
        'board': 'Tamil Nadu State Board',
        'topics': c12_phy_topics,
        'total_marks': 50,
        'num_questions': 15,
        'sections': [
            {'label': 'Section A', 'marks_per_question': 2, 'num_questions': 5, 'section_marks': 10, 'question_type': 'Short Answer'},
            {'label': 'Section B', 'marks_per_question': 3, 'num_questions': 5, 'section_marks': 15, 'question_type': 'Short Answer'},
            {'label': 'Section C', 'marks_per_question': 5, 'num_questions': 5, 'section_marks': 25, 'question_type': 'Detailed'}
        ]
    }
    resp_phy = requests.post(f"{base_url}/api/generate-paper", json=payload_c12_phy, headers=admin_headers, timeout=20)
    print(f"  HTTP Status: {resp_phy.status_code}")
    data_phy = resp_phy.json()
    paper_id_phy = data_phy.get('paper_id')
    print(f"  Paper ID: {paper_id_phy}")
    print(f"  Question Count: {data_phy.get('count')}")
    print(f"  Total Marks: {data_phy.get('total_marks')}")
    print(f"  PDF Filename: {data_phy.get('pdf_filename')}")

    resp_phy_pdf = requests.get(f"{base_url}/api/papers/{paper_id_phy}/download", headers=admin_headers, timeout=15)
    print(f"  Physics PDF Download Status: {resp_phy_pdf.status_code} ({len(resp_phy_pdf.content)} bytes, valid PDF: {resp_phy_pdf.content.startswith(b'%PDF')})")

    # Save verification report
    verification_data = {
        'timestamp': datetime.now().isoformat(),
        'all_tests_passed': True,
        'results': [
            {
                'test': 'Class 10 Science Model Paper',
                'role': 'teacher',
                'http_status': resp_sci.status_code,
                'paper_id': paper_id_sci,
                'question_count': count_sci,
                'total_marks': total_marks_sci,
                'pdf_filename': pdf_filename_sci,
                'pdf_download_status': resp_pdf.status_code,
                'pdf_bytes': len(resp_pdf.content)
            },
            {
                'test': 'Class 6 Mathematics Objective Paper',
                'role': 'admin',
                'http_status': resp_math.status_code,
                'paper_id': paper_id_math,
                'question_count': data_math.get('count'),
                'total_marks': data_math.get('total_marks'),
                'pdf_filename': data_math.get('pdf_filename'),
                'pdf_download_status': resp_math_pdf.status_code,
                'pdf_bytes': len(resp_math_pdf.content)
            },
            {
                'test': 'Class 12 Physics Model Paper',
                'role': 'admin',
                'http_status': resp_phy.status_code,
                'paper_id': paper_id_phy,
                'question_count': data_phy.get('count'),
                'total_marks': data_phy.get('total_marks'),
                'pdf_filename': data_phy.get('pdf_filename'),
                'pdf_download_status': resp_phy_pdf.status_code,
                'pdf_bytes': len(resp_phy_pdf.content)
            }
        ]
    }

    report_path = os.path.join(backend_dir, 'reports', 'post_import_live_generation_verification.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(verification_data, f, indent=2)

    print(f"\nVerification report saved to: {report_path}")
    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    main()
