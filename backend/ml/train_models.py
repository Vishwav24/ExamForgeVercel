"""
Supervised Machine Learning Training Pipelines for ExamForge AI
Trains two independent text-classification pipelines:
- Model A: Bloom's Taxonomy Classifier (6 Cognitive Dimensions)
- Model B: Difficulty Classifier (Easy, Medium, Hard)

Key Principles:
1. Pure scikit-learn Pipeline (TfidfVectorizer + LogisticRegression).
2. Strict fit only on training data (prevent data leakage).
3. 80/20 Stratified train/test split with reproducible random seed.
4. Baseline comparison (Majority-class classifier).
5. Comprehensive evaluation metrics & confusion matrices saved as JSON reports.
6. Pipeline persistence via Joblib.
7. Critical notes regarding template-induced leakage & real-world generalization limits.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from collections import Counter
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)

# Relative directory resolution from script location to project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MODELS_DIR = os.path.join(BASE_DIR, 'models')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

CSV_PATH = os.path.join(DATA_DIR, 'questions_dataset.csv')
BLOOM_MODEL_PATH = os.path.join(MODELS_DIR, 'bloom_model.joblib')
DIFFICULTY_MODEL_PATH = os.path.join(MODELS_DIR, 'difficulty_model.joblib')
BLOOM_REPORT_PATH = os.path.join(REPORTS_DIR, 'bloom_evaluation.json')
DIFFICULTY_REPORT_PATH = os.path.join(REPORTS_DIR, 'difficulty_evaluation.json')
TRAINING_SUMMARY_PATH = os.path.join(REPORTS_DIR, 'training_summary.json')

RANDOM_SEED = 42
TEST_SIZE = 0.20
MIN_CLASS_SAMPLES = 10

EXPECTED_BLOOM_CLASSES = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
EXPECTED_DIFFICULTY_CLASSES = ['Easy', 'Medium', 'Hard']


def ensure_directories():
    """Ensure output directories exist."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


def evaluate_pipeline(pipeline, baseline_model, X_train, y_train, X_test, y_test, class_labels, task_name):
    """
    Evaluate fitted pipeline and compare against majority baseline.
    Returns structured evaluation dictionary.
    """
    print(f"Evaluating {task_name} on held-out test data ({len(X_test):,} samples)...")
    
    # Model predictions
    y_pred = pipeline.predict(X_test)
    
    # Majority baseline predictions
    baseline_pred = baseline_model.predict(X_test)
    baseline_acc = float(accuracy_score(y_test, baseline_pred))
    baseline_macro_f1 = float(f1_score(y_test, baseline_pred, average='macro', zero_division=0))

    # Test metrics
    acc = float(accuracy_score(y_test, y_pred))
    macro_prec = float(precision_score(y_test, y_pred, average='macro', zero_division=0))
    macro_rec = float(recall_score(y_test, y_pred, average='macro', zero_division=0))
    macro_f1 = float(f1_score(y_test, y_pred, average='macro', zero_division=0))
    weighted_f1 = float(f1_score(y_test, y_pred, average='weighted', zero_division=0))

    # Per-class report
    clf_report = classification_report(
        y_test, y_pred, labels=class_labels, output_dict=True, zero_division=0
    )

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred, labels=class_labels)
    cm_dict = {
        "labels": class_labels,
        "matrix": cm.tolist()
    }

    # Per-class metrics dict
    per_class_metrics = {}
    for label in class_labels:
        if label in clf_report:
            per_class_metrics[label] = {
                "precision": round(float(clf_report[label]['precision']), 4),
                "recall": round(float(clf_report[label]['recall']), 4),
                "f1-score": round(float(clf_report[label]['f1-score']), 4),
                "support": int(clf_report[label]['support'])
            }

    print(f"\n--- {task_name} Results ---")
    print(f"  • Test Accuracy:        {acc:.4f}  (Majority Baseline: {baseline_acc:.4f})")
    print(f"  • Macro F1-Score:       {macro_f1:.4f}  (Majority Baseline: {baseline_macro_f1:.4f})")
    print(f"  • Macro Precision:      {macro_prec:.4f}")
    print(f"  • Macro Recall:         {macro_rec:.4f}")
    print(f"  • Weighted F1-Score:    {weighted_f1:.4f}")

    eval_result = {
        "task": task_name,
        "test_size": len(X_test),
        "train_size": len(X_train),
        "classes": class_labels,
        "accuracy": round(acc, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "baseline_comparison": {
            "strategy": "most_frequent",
            "baseline_accuracy": round(baseline_acc, 4),
            "baseline_macro_f1": round(baseline_macro_f1, 4)
        },
        "per_class": per_class_metrics,
        "confusion_matrix": cm_dict,
        "generalization_warning": (
            "Notice: Evaluation was performed on an 80/20 held-out split of the provided question bank. "
            "However, synthetic or repeated syntactic question templates within the dataset may cause "
            "lexical overlap between train and test splits, artificially elevating held-out scores. "
            "This metric demonstrates pipeline convergence on this corpus, not guaranteed out-of-domain "
            "real-world generalization across unseen boards or question styles."
        )
    }
    return eval_result


def train_bloom_pipeline(df):
    """Train Model A: Bloom's Taxonomy Classifier."""
    print("\n" + "=" * 70)
    print("STEP 2: Training Model A — Bloom's Taxonomy Classifier")
    print("=" * 70)

    # Filter and validate valid records
    valid_mask = df['bloom_level'].isin(EXPECTED_BLOOM_CLASSES) & df['question'].notna()
    subset = df[valid_mask].copy()

    if len(subset) == 0:
        raise ValueError("No valid questions found for Bloom classification.")

    X = np.array(subset['question'].astype(str).tolist(), dtype=object)
    y = np.array(subset['bloom_level'].astype(str).tolist(), dtype=object)

    class_counts = Counter(y)
    print(f"Class distribution ({len(subset):,} samples):")
    for cls in EXPECTED_BLOOM_CLASSES:
        cnt = class_counts.get(cls, 0)
        print(f"  • {cls:12s}: {cnt:6d}")
        if cnt < MIN_CLASS_SAMPLES:
            raise ValueError(f"Insufficient samples for class '{cls}': {cnt} < {MIN_CLASS_SAMPLES}")

    # Stratified 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y
    )
    print(f"Split sizes: Train={len(X_train):,}, Held-out Test={len(X_test):,}")

    # Define Pipeline: TF-IDF + LogisticRegression
    # Note: TfidfVectorizer fits only on X_train during pipeline.fit()
    bloom_pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=12000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True
        )),
        ('clf', LogisticRegression(
            max_iter=1000,
            random_state=RANDOM_SEED,
            class_weight='balanced',
            C=1.0,
            solver='lbfgs'
        ))
    ])

    # Fit baseline
    baseline = DummyClassifier(strategy='most_frequent')
    baseline.fit(X_train, y_train)

    # Fit ML Pipeline
    start_time = time.time()
    bloom_pipeline.fit(X_train, y_train)
    duration = time.time() - start_time
    print(f"Bloom pipeline training completed in {duration:.2f} seconds.")

    # Evaluate
    bloom_eval = evaluate_pipeline(
        bloom_pipeline, baseline, X_train, y_train, X_test, y_test,
        EXPECTED_BLOOM_CLASSES, "Bloom's Taxonomy Classification"
    )
    bloom_eval["training_duration_seconds"] = round(duration, 2)

    return bloom_pipeline, bloom_eval


def train_difficulty_pipeline(df):
    """Train Model B: Difficulty Classifier."""
    print("\n" + "=" * 70)
    print("STEP 3: Training Model B — Difficulty Classifier")
    print("=" * 70)

    valid_mask = df['difficulty'].isin(EXPECTED_DIFFICULTY_CLASSES) & df['question'].notna()
    subset = df[valid_mask].copy()

    if len(subset) == 0:
        raise ValueError("No valid questions found for Difficulty classification.")

    X = np.array(subset['question'].astype(str).tolist(), dtype=object)
    y = np.array(subset['difficulty'].astype(str).tolist(), dtype=object)

    class_counts = Counter(y)
    print(f"Class distribution ({len(subset):,} samples):")
    for cls in EXPECTED_DIFFICULTY_CLASSES:
        cnt = class_counts.get(cls, 0)
        print(f"  • {cls:12s}: {cnt:6d}")
        if cnt < MIN_CLASS_SAMPLES:
            raise ValueError(f"Insufficient samples for difficulty '{cls}': {cnt} < {MIN_CLASS_SAMPLES}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y
    )
    print(f"Split sizes: Train={len(X_train):,}, Held-out Test={len(X_test):,}")

    diff_pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True
        )),
        ('clf', LogisticRegression(
            max_iter=1000,
            random_state=RANDOM_SEED,
            class_weight='balanced',
            C=1.0,
            solver='lbfgs'
        ))
    ])

    baseline = DummyClassifier(strategy='most_frequent')
    baseline.fit(X_train, y_train)

    start_time = time.time()
    diff_pipeline.fit(X_train, y_train)
    duration = time.time() - start_time
    print(f"Difficulty pipeline training completed in {duration:.2f} seconds.")

    diff_eval = evaluate_pipeline(
        diff_pipeline, baseline, X_train, y_train, X_test, y_test,
        EXPECTED_DIFFICULTY_CLASSES, "Difficulty Classification"
    )
    diff_eval["training_duration_seconds"] = round(duration, 2)

    return diff_pipeline, diff_eval


def main():
    print("=" * 70)
    print("  ExamForge AI — Supervised Machine Learning Pipeline Training")
    print("=" * 70)

    ensure_directories()

    # 1. Load dataset
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"Dataset not found at '{CSV_PATH}'.\n"
            f"Run 'python backend/data/download_dataset.py' to generate the cleaned dataset."
        )

    print(f"Loading cleaned dataset: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df):,} records across {len(df.columns)} columns.")

    # 2. Check required columns
    required_cols = ['question', 'bloom_level', 'difficulty']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Dataset is missing required columns: {missing_cols}")

    # 3. Train Model A: Bloom Classifier
    bloom_pipeline, bloom_eval = train_bloom_pipeline(df)

    # 4. Train Model B: Difficulty Classifier
    diff_pipeline, diff_eval = train_difficulty_pipeline(df)

    # 5. Save Model Artifacts
    print("\n" + "=" * 70)
    print("STEP 4: Saving Trained Model Pipelines and Evaluation Reports")
    print("=" * 70)

    joblib.dump(bloom_pipeline, BLOOM_MODEL_PATH)
    print(f"✓ Saved Bloom's Taxonomy Pipeline: {BLOOM_MODEL_PATH}")

    joblib.dump(diff_pipeline, DIFFICULTY_MODEL_PATH)
    print(f"✓ Saved Difficulty Pipeline:        {DIFFICULTY_MODEL_PATH}")

    with open(BLOOM_REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(bloom_eval, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved Bloom Evaluation Report:   {BLOOM_REPORT_PATH}")

    with open(DIFFICULTY_REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(diff_eval, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved Difficulty Evaluation:     {DIFFICULTY_REPORT_PATH}")

    # 6. Save Training Summary
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "random_seed": RANDOM_SEED,
        "test_size_fraction": TEST_SIZE,
        "dataset_path": "backend/data/questions_dataset.csv",
        "total_dataset_rows": len(df),
        "models": {
            "bloom_taxonomy": {
                "pipeline": "TfidfVectorizer + LogisticRegression",
                "artifact": "backend/models/bloom_model.joblib",
                "classes": EXPECTED_BLOOM_CLASSES,
                "train_samples": bloom_eval["train_size"],
                "test_samples": bloom_eval["test_size"],
                "accuracy": bloom_eval["accuracy"],
                "macro_f1": bloom_eval["macro_f1"],
                "baseline_accuracy": bloom_eval["baseline_comparison"]["baseline_accuracy"]
            },
            "difficulty": {
                "pipeline": "TfidfVectorizer + LogisticRegression",
                "artifact": "backend/models/difficulty_model.joblib",
                "classes": EXPECTED_DIFFICULTY_CLASSES,
                "train_samples": diff_eval["train_size"],
                "test_samples": diff_eval["test_size"],
                "accuracy": diff_eval["accuracy"],
                "macro_f1": diff_eval["macro_f1"],
                "baseline_accuracy": diff_eval["baseline_comparison"]["baseline_accuracy"]
            }
        },
        "generalization_caveat": (
            "Caution: Held-out performance reflects internal dataset consistency. "
            "Repetitive template structures in public question corpora may inflate test metrics. "
            "Teacher verification of predicted labels remains recommended."
        )
    }

    with open(TRAINING_SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved Training Summary:          {TRAINING_SUMMARY_PATH}")

    print("\n" + "=" * 70)
    print("ALL ML TRAINING TASKS COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == '__main__':
    main()
