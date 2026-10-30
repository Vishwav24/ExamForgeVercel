import os
import sys
import pandas as pd

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(backend_dir, 'data')

print("=== CHECKING ALL STAGING & CANDIDATE CSVs FOR CLASS 10 MATHEMATICS 2-MARK ===")

for root, dirs, files in os.walk(data_dir):
    for f in files:
        if f.endswith('.csv'):
            path = os.path.join(root, f)
            try:
                df = pd.read_csv(path, low_memory=False)
                # check if class_grade or standard exists
                cg_col = next((c for c in df.columns if c in ['class_grade', 'standard', 'class']), None)
                sub_col = next((c for c in df.columns if c in ['subject', 'subject_name']), None)
                marks_col = next((c for c in df.columns if c in ['suggested_marks', 'marks']), None)
                
                if cg_col and sub_col and marks_col:
                    mask = (df[cg_col].astype(str).str.contains('10')) & (df[sub_col].astype(str).str.lower() == 'mathematics')
                    math_rows = df[mask]
                    if len(math_rows) > 0:
                        m2_rows = math_rows[math_rows[marks_col].astype(str).isin(['2', '2.0'])]
                        print(f"File: {path}")
                        print(f"  Class 10 Math total: {len(math_rows)}, 2-mark: {len(m2_rows)}")
                        if len(m2_rows) > 0:
                            for _, r in m2_rows.head(5).iterrows():
                                q_text = r.get('question_text') or r.get('question')
                                ch = r.get('chapter_heading') or r.get('topic')
                                val = r.get('validation_status')
                                print(f"    - [{ch}] {str(q_text)[:70]} | status: {val}")
            except Exception as e:
                pass

