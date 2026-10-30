"""
Dataset Quality Inspection Script for ExamForge AI
Analyzes backend/data/questions_dataset.csv before ML training.

Performs:
1. Shape and column verification.
2. Missing values and exact duplicate analysis.
3. Class frequency distributions and percentages (Bloom Taxonomy & Difficulty).
4. Example questions for each class (at least 5 per class).
5. Template / linguistic pattern inspection for repetitive syntactic structures.
6. Diversity inspection across subjects, topics, and question types.
7. Stratification suitability check for train/test splits.
8. JSON export to backend/reports/data_inspection.json without altering source data.
"""

import os
import sys
import json
import re
from collections import Counter
import pandas as pd
import numpy as np

# Resolve project base directory relative to this script
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

CSV_PATH = os.path.join(DATA_DIR, 'questions_dataset.csv')
REPORT_PATH = os.path.join(REPORTS_DIR, 'data_inspection.json')

# Target taxonomy & difficulty definitions
BLOOM_CLASSES = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
DIFFICULTY_CLASSES = ['Easy', 'Medium', 'Hard']

# Minimum class count recommended for a reliable stratified 80/20 train/test split
MIN_STRATIFY_THRESHOLD = 50


def inspect_templates(questions, max_samples=20000):
    """
    Detect recurring prompt/question templates by replacing specific nouns/terms
    and extracting common initial grammatical prefixes (e.g., 'What is...', 'Explain the...').
    """
    templates = Counter()
    for q in questions[:max_samples]:
        if not isinstance(q, str):
            continue
        # Extract the opening 3 to 5 words as a question template signature
        words = q.strip().split()
        if len(words) >= 4:
            prefix = " ".join(words[:4]).lower()
            # Clean punctuation for grouping
            prefix = re.sub(r'[^a-z0-9\s]', '', prefix).strip()
            templates[prefix] += 1

    top_templates = [
        {"template_prefix": t, "occurrences": count}
        for t, count in templates.most_common(10)
        if count > 5
    ]
    return top_templates


def run_inspection():
    print("=" * 70)
    print("  ExamForge AI — Machine Learning Dataset Quality Inspection")
    print("=" * 70)

    # 1. Path check
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"Dataset CSV not found at '{CSV_PATH}'.\n"
            f"Please run 'python backend/data/download_dataset.py' first."
        )

    print(f"Reading dataset: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)

    # 2. Dataset Shape and Column Names
    rows, cols = df.shape
    columns = list(df.columns)
    print(f"\n[1] Basic Structure")
    print(f"    • Total Rows:    {rows:,}")
    print(f"    • Total Columns: {cols}")
    print(f"    • Column Names:  {columns}")

    # 3. Missing values & Duplicates
    print(f"\n[2] Missing Values & Duplicates")
    missing_counts = {col: int(df[col].isna().sum()) for col in columns}
    for col, count in missing_counts.items():
        pct = (count / rows * 100) if rows > 0 else 0.0
        print(f"    • {col:15s}: {count:6d} missing ({pct:5.2f}%)")

    exact_full_duplicates = int(df.duplicated().sum())
    question_text_duplicates = 0
    if 'question' in df.columns:
        question_text_duplicates = int(df['question'].duplicated().sum())

    print(f"    • Exact Duplicate Rows:       {exact_full_duplicates}")
    print(f"    • Duplicate Question Texts:    {question_text_duplicates}")

    # 4. Bloom Taxonomy Distribution
    print(f"\n[3] Bloom's Taxonomy Label Distribution")
    bloom_dist = {}
    if 'bloom_level' in df.columns:
        bloom_counts = df['bloom_level'].value_counts()
        for level in BLOOM_CLASSES:
            cnt = int(bloom_counts.get(level, 0))
            pct = (cnt / rows * 100) if rows > 0 else 0.0
            bloom_dist[level] = {"count": cnt, "percentage": round(pct, 2)}
            print(f"    • {level:12s}: {cnt:6d} ({pct:5.2f}%)")
    else:
        print("    [!] 'bloom_level' column missing from dataset!")

    # 5. Difficulty Label Distribution
    print(f"\n[4] Difficulty Label Distribution")
    difficulty_dist = {}
    if 'difficulty' in df.columns:
        diff_counts = df['difficulty'].value_counts()
        for diff in DIFFICULTY_CLASSES:
            cnt = int(diff_counts.get(diff, 0))
            pct = (cnt / rows * 100) if rows > 0 else 0.0
            difficulty_dist[diff] = {"count": cnt, "percentage": round(pct, 2)}
            print(f"    • {diff:12s}: {cnt:6d} ({pct:5.2f}%)")
    else:
        print("    [!] 'difficulty' column missing from dataset!")

    # 6. Sample Questions Per Class (At least 5)
    print(f"\n[5] Example Questions per Target Class")
    bloom_examples = {}
    if 'question' in df.columns and 'bloom_level' in df.columns:
        for level in BLOOM_CLASSES:
            subset = df[df['bloom_level'] == level]['question'].dropna()
            samples = subset.head(5).tolist()
            bloom_examples[level] = samples
            print(f"\n    --- Bloom Level: {level} (Showing {len(samples)} examples) ---")
            for i, ex in enumerate(samples, 1):
                clean_ex = (ex[:110] + '...') if len(ex) > 110 else ex
                print(f"      {i}. {clean_ex}")

    diff_examples = {}
    if 'question' in df.columns and 'difficulty' in df.columns:
        for diff in DIFFICULTY_CLASSES:
            subset = df[df['difficulty'] == diff]['question'].dropna()
            samples = subset.head(5).tolist()
            diff_examples[diff] = samples
            print(f"\n    --- Difficulty: {diff} (Showing {len(samples)} examples) ---")
            for i, ex in enumerate(samples, 1):
                clean_ex = (ex[:110] + '...') if len(ex) > 110 else ex
                print(f"      {i}. {clean_ex}")

    # 7. Metadata Diversity: Subjects, Topics, Question Types
    print(f"\n[6] Metadata Diversity Analysis")
    metadata_diversity = {}
    for meta_col in ['subject', 'topic', 'question_type']:
        if meta_col in df.columns:
            unique_count = int(df[meta_col].nunique())
            top_items = df[meta_col].value_counts().head(5).to_dict()
            metadata_diversity[meta_col] = {
                "unique_values": unique_count,
                "top_5": {str(k): int(v) for k, v in top_items.items()}
            }
            print(f"    • {meta_col:15s}: {unique_count} distinct values")
            for k, v in list(top_items.items())[:3]:
                print(f"       - {k}: {v} questions")

    # 8. Template & Syntactic Pattern Inspection
    print(f"\n[7] Repetitive Template & Syntax Analysis")
    templates = []
    if 'question' in df.columns:
        templates = inspect_templates(df['question'].tolist())
        for item in templates[:5]:
            print(f"    • Pattern '{item['template_prefix']}...': {item['occurrences']} times")

    # 9. Stratification Feasibility Check
    print(f"\n[8] Train/Test Stratification Feasibility")
    underrepresented_bloom = [
        lvl for lvl, data in bloom_dist.items() if data['count'] < MIN_STRATIFY_THRESHOLD
    ]
    underrepresented_diff = [
        d for d, data in difficulty_dist.items() if data['count'] < MIN_STRATIFY_THRESHOLD
    ]

    stratify_bloom_ok = len(underrepresented_bloom) == 0
    stratify_diff_ok = len(underrepresented_diff) == 0

    print(f"    • Bloom Stratification (Threshold >= {MIN_STRATIFY_THRESHOLD}): {'SUITABLE' if stratify_bloom_ok else 'INSUFFICIENT'}")
    if not stratify_bloom_ok:
        print(f"      [!] Classes with too few examples: {underrepresented_bloom}")

    print(f"    • Difficulty Stratification (Threshold >= {MIN_STRATIFY_THRESHOLD}): {'SUITABLE' if stratify_diff_ok else 'INSUFFICIENT'}")
    if not stratify_diff_ok:
        print(f"      [!] Classes with too few examples: {underrepresented_diff}")

    # 10. Generate & Save Inspection Report
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_data = {
        "dataset_path": "backend/data/questions_dataset.csv",
        "dataset_shape": {"rows": rows, "columns": cols},
        "columns": columns,
        "missing_values": missing_counts,
        "exact_duplicates": exact_full_duplicates,
        "question_text_duplicates": question_text_duplicates,
        "bloom_distribution": bloom_dist,
        "difficulty_distribution": difficulty_dist,
        "bloom_examples": bloom_examples,
        "difficulty_examples": diff_examples,
        "metadata_diversity": metadata_diversity,
        "top_question_templates": templates,
        "stratification_feasibility": {
            "minimum_recommended_samples": MIN_STRATIFY_THRESHOLD,
            "bloom_taxonomy_suitable": stratify_bloom_ok,
            "underrepresented_bloom_classes": underrepresented_bloom,
            "difficulty_suitable": stratify_diff_ok,
            "underrepresented_difficulty_classes": underrepresented_diff
        }
    }

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"\n" + "=" * 70)
    print(f"✓ Quality inspection report successfully written to:")
    print(f"  {REPORT_PATH}")
    print("=" * 70)


if __name__ == '__main__':
    run_inspection()
