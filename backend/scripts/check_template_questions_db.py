import sqlite3
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(backend_dir, 'database', 'examforge.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, question_id, class_grade, subject, topic, marks, question FROM questions WHERE question LIKE '%State the core definitions, formulas, and conditions related to%'")
rows = c.fetchall()
print(f"Total rows matching template: {len(rows)}")
for r in rows:
    print(r)

