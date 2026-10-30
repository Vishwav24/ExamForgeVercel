import sys, os
import urllib.request
import json

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from database.db import SessionLocal
from database.models import User
from services.auth import create_access_token

# 1. Fetch teacher from live DB and create valid signed token
db = SessionLocal()
teacher = db.query(User).filter_by(email='teacher@examforge.ai').first()
token = create_access_token(teacher)
db.close()

# 2. Test /api/generate-paper against the actual live running backend (Port 5000)
generate_url = 'http://localhost:5000/api/generate-paper'
payload = {
    'title': 'Tamil Nadu State Board Mid-Term Examination 2026',
    'board': 'Tamil Nadu State Board',
    'class_grade': 'Class 10',
    'subject': 'Science',
    'chapters': [
        'Laws of Motion', 'Optics', 'Thermal Physics', 'Electricity', 'Acoustics',
        'Nuclear Physics', 'Atoms and Molecules', 'Periodic Classification of Elements',
        'Solutions', 'Types of Chemical Reactions', 'Carbon and its Compounds',
        'Plant Anatomy and Plant Physiology', 'Structural Organisation of Animals',
        'Transportation in Plants and Circulation in Animals', 'Nervous System',
        'Plant and Animal Hormones', 'Reproduction in Plants and Animals', 'Heredity',
        'Origin and Evolution of Life', 'Breeding and Biotechnology', 'Environmental Management'
    ],
    'duration_minutes': 90,
    'total_marks': 50,
    'num_questions': 15,
    'sections': [
        {'marks_per_question': 2, 'num_questions': 5},
        {'marks_per_question': 3, 'num_questions': 5},
        {'marks_per_question': 5, 'num_questions': 5}
    ],
    'difficulty_distribution': {'Easy': 30, 'Medium': 50, 'Hard': 20},
    'bloom_distribution': {'Remember': 25, 'Understand': 30, 'Apply': 20, 'Analyze': 15, 'Evaluate': 5, 'Create': 5}
}

req = urllib.request.Request(
    generate_url,
    data=json.dumps(payload).encode('utf-8'),
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
)

try:
    with urllib.request.urlopen(req) as response:
        status_code = response.status
        res_data = json.loads(response.read().decode('utf-8'))
        print('HTTP Status:', status_code)
        print('Response JSON:', json.dumps(res_data, indent=2))
except urllib.error.HTTPError as e:
    status_code = e.code
    res_body = e.read().decode('utf-8')
    print('HTTP Status:', status_code)
    try:
        err_json = json.loads(res_body)
        print('Response JSON:', json.dumps(err_json, indent=2))
    except Exception:
        print('Response Body:', res_body)
