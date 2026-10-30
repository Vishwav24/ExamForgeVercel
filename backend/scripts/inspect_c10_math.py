import sqlite3
import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(backend_dir, 'database', 'examforge.db')

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, question_id, question, topic, marks, question_type, bloom_level, difficulty, source, verified, board FROM questions WHERE class_grade = 'Class 10' AND subject = 'Mathematics'")
rows = c.fetchall()
print(f"Total Class 10 Mathematics questions in DB: {len(rows)}")

by_marks = {}
by_topic = {}
for r in rows:
    m = r[4]
    t = r[3]
    by_marks[m] = by_marks.get(m, 0) + 1
    by_topic[t] = by_topic.get(t, 0) + 1

print("By marks:", by_marks)
print("By topic:", by_topic)

print("\n--- All Class 10 Mathematics 2-mark questions in DB ---")
two_m = [r for r in rows if r[4] == 2.0]
print(f"Count of 2-mark questions: {len(two_m)}")
for r in two_m:
    print(f"ID: {r[0]} | QID: {r[1]} | Topic: {r[3]} | Board: {r[10]} | Verified: {r[9]} | Source: {r[8]}")
    print(f"  Question: {r[2]}")

print("\n--- Check all non-1m questions in Class 10 Mathematics ---")
non_1m = [r for r in rows if r[4] != 1.0]
print(f"Count of non-1m questions: {len(non_1m)}")
for r in non_1m:
    print(f"ID: {r[0]} | {r[4]}m | {r[5]} | Topic: {r[3]} | Q: {r[2]}")

print("\n--- Check candidates CSVs or staging files for Class 10 Mathematics 2-mark ---")
c10_csv = os.path.join(backend_dir, 'data', 'extracted_candidates_v2', 'candidates_class_10.csv')
if os.path.exists(c10_csv):
    import pandas as pd
    df = pd.read_csv(c10_csv, low_memory=False)
    math_df = df[df['subject'] == 'Mathematics']
    print(f"In candidates_class_10.csv, Math count: {len(math_df)}")
    print("Math by marks in CSV:", math_df['suggested_marks'].value_counts().to_dict() if 'suggested_marks' in math_df else math_df['marks'].value_counts().to_dict())

    # Check 2m candidates in CSV
    m_col = 'suggested_marks' if 'suggested_marks' in math_df else 'marks'
    math_2m = math_df[math_df[m_col] == 2.0]
    print(f"Math 2m in CSV: {len(math_2m)}")
    for idx, row in math_2m.iterrows():
        print(f"  CSV 2m: {row.get('candidate_id')} | Topic: {row.get('chapter_heading')} | Q: {str(row.get('question_text'))[:60]}")

conn.close()

