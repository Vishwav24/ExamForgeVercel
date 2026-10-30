import sqlite3
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(backend_dir, 'database', 'examforge.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, class_grade, subject, topic, marks, question FROM questions WHERE (class_grade LIKE '%10%' OR class_grade LIKE '%Ten%') AND (subject LIKE '%Math%' OR subject LIKE '%கணிதம்%') AND marks = 2.0")
rows = c.fetchall()
print(f"Total matching 2m math rows in DB: {len(rows)}")
for r in rows:
    print(r)

