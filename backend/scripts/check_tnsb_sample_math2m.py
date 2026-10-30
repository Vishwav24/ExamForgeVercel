import os
import pandas as pd

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_path = os.path.join(backend_dir, 'data', 'tamilnadu_state_board_sample.csv')

df = pd.read_csv(csv_path)
mask = (df['class_grade'] == 'Class 10') & (df['subject'] == 'Mathematics') & (df['marks'] == 2.0)
m2 = df[mask]
print(f"Total 2-mark in tamilnadu_state_board_sample.csv: {len(m2)}")
for idx, r in m2.iterrows():
    print(f"Row {idx} | Topic: {r['topic']} | Q: {r['question']}")

