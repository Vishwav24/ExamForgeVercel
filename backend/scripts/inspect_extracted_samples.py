import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('backend/data/extracted_candidates/candidates_all_standards.json', 'r', encoding='utf-8') as f:
    cands = json.load(f)

# Sample 1: Class 10 Tamil
print('=== Class 10 Tamil Samples ===')
tam_10 = [c for c in cands if c['class_grade'] == 'Class 10' and c['subject'] == 'Tamil'][:6]
for c in tam_10:
    print(f"ID: {c['candidate_id']} | Type: {c['question_type']} | Marks: {c['suggested_marks']} | Status: {c['validation_status']}")
    print(f"Stem: {c['question_text']}")
    if c['options']:
        print(f"Options ({len(c['options'])}):")
        for o in c['options']:
            print(f"   {o['label']}) {o['text']}")
    print()

# Sample 2: Class 8 English Social Science
print('=== Class 8 English Social Science Samples ===')
soc_8 = [c for c in cands if c['class_grade'] == 'Class 8' and c['subject'] == 'Social Science' and c['medium'] == 'English'][:4]
for c in soc_8:
    print(f"ID: {c['candidate_id']} | Type: {c['question_type']} | Marks: {c['suggested_marks']} | Status: {c['validation_status']}")
    print(f"Stem: {c['question_text']}")
    if c['options']:
        print(f"Options ({len(c['options'])}):")
        for o in c['options']:
            print(f"   {o['label']}) {o['text']}")
    print()

# Sample 3: Class 12 Tamil Chemistry
print('=== Class 12 Tamil Chemistry Samples ===')
chem_12 = [c for c in cands if c['class_grade'] == 'Class 12' and c['subject'] == 'Chemistry' and c['medium'] == 'Tamil'][:3]
for c in chem_12:
    print(f"ID: {c['candidate_id']} | Type: {c['question_type']} | Marks: {c['suggested_marks']} | Status: {c['validation_status']}")
    print(f"Stem: {c['question_text']}")
    if c['options']:
        print(f"Options ({len(c['options'])}):")
        for o in c['options']:
            print(f"   {o['label']}) {o['text']}")
    print()

