#!/usr/bin/env python3
"""
ExamForge AI - Local Machine Learning Training CLI (VS Code Workflow)
Tamil Nadu State Board & EduBloom Question Classification

Trains supervised NLP classifiers for:
  - Task 1: Bloom's Taxonomy (6 Cognitive Dimensions: Remember, Understand, Apply, Analyze, Evaluate, Create)
  - Task 2: Difficulty Level (Easy, Medium, Hard)

Features:
  - Hugging Face dataset download ('Uzaib52/edubloom-question-bank') or local CSV fallback
  - Automatic column detection & taxonomy standardization (L1-L6 -> Remember..Create)
  - Stratified 80/20 train/test split with template leakage prevention
  - TF-IDF + Random Forest Pipeline with balanced class weights
  - Honest held-out test evaluation: Accuracy, Precision, Recall, Macro/Weighted F1, Confusion Matrix
  - Versioned .joblib model artifacts in backend/models/
  - Structured JSON evaluation reports in backend/reports/
  - Optional production activation (--activate)

Usage Examples in VS Code / PowerShell:
  python backend/ml/train_local.py --task bloom
  python backend/ml/train_local.py --task difficulty
  python backend/ml/train_local.py --task all --sample-limit 15000
  python backend/ml/train_local.py --source hf --task all
  python backend/ml/train_local.py --source combined --task bloom --activate
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
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

# Project path resolution
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

DATA_DIR = os.path.join(BACKEND_DIR, 'data')
MODELS_DIR = os.path.join(BACKEND_DIR, 'models')
REPORTS_DIR = os.path.join(BACKEND_DIR, 'reports')

DEFAULT_LOCAL_CSV = os.path.join(DATA_DIR, 'questions_dataset.csv')
DEFAULT_COMBINED_CSV = os.path.join(DATA_DIR, 'combined_training_dataset.csv')
DEFAULT_TN_CSV = os.path.join(DATA_DIR, 'tamilnadu_state_board_sample.csv')
DEFAULT_HF_REPO = 'Uzaib52/edubloom-question-bank'

BLOOM_CLASSES = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
DIFFICULTY_CLASSES = ['Easy', 'Medium', 'Hard']

BLOOM_NORMALIZATION_MAP = {
    'l1': 'Remember', '1': 'Remember', 'remember': 'Remember', 'remembering': 'Remember', 'knowledge': 'Remember',
    'l2': 'Understand', '2': 'Understand', 'understand': 'Understand', 'understanding': 'Understand', 'comprehension': 'Understand',
    'l3': 'Apply', '3': 'Apply', 'apply': 'Apply', 'applying': 'Apply', 'application': 'Apply',
    'l4': 'Analyze', '4': 'Analyze', 'analyze': 'Analyze', 'analysing': 'Analyze', 'analysis': 'Analyze',
    'l5': 'Evaluate', '5': 'Evaluate', 'evaluate': 'Evaluate', 'evaluating': 'Evaluate', 'evaluation': 'Evaluate',
    'l6': 'Create', '6': 'Create', 'create': 'Create', 'creating': 'Create', 'synthesis': 'Create'
}

DIFFICULTY_NORMALIZATION_MAP = {
    'easy': 'Easy', '0': 'Easy', 'low': 'Easy', 'simple': 'Easy',
    'medium': 'Medium', '1': 'Medium', 'med': 'Medium', 'moderate': 'Medium', 'intermediate': 'Medium',
    'hard': 'Hard', '2': 'Hard', 'high': 'Hard', 'difficult': 'Hard', 'advanced': 'Hard'
}


def log_step(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def load_dataset_source(source_type, dataset_arg=None, download_hf=False):
    """
    Loads raw dataset from local CSV, combined CSV, or Hugging Face.
    """
    log_step(f"Step 1: Loading Dataset (Source: {source_type.upper()})")

    df = None

    if download_hf or source_type == 'hf':
        hf_repo = dataset_arg or DEFAULT_HF_REPO
        print(f"[*] Attempting to fetch dataset from Hugging Face: {hf_repo}...")
        try:
            from datasets import load_dataset
            hf_ds = load_dataset(hf_repo)
            # Combine all splits (e.g. train) into pandas DataFrame
            splits = list(hf_ds.keys())
            print(f"[+] Successfully connected to Hugging Face! Found splits: {splits}")
            frames = [hf_ds[split].to_pandas() for split in splits]
            df = pd.concat(frames, ignore_index=True)
            print(f"[+] Loaded {len(df):,} rows directly from Hugging Face '{hf_repo}'.")
        except Exception as e:
            print(f"[!] Warning: Hugging Face download failed ({e}).")
            print(f"[*] Falling back to local offline EduBloom CSV cache: {DEFAULT_LOCAL_CSV}")
            if os.path.exists(DEFAULT_LOCAL_CSV):
                df = pd.read_csv(DEFAULT_LOCAL_CSV)
                print(f"[+] Loaded {len(df):,} rows from local fallback {DEFAULT_LOCAL_CSV}.")
            else:
                raise FileNotFoundError(f"Could not load Hugging Face dataset or fallback {DEFAULT_LOCAL_CSV}.")

    elif source_type == 'combined':
        target_path = dataset_arg or DEFAULT_COMBINED_CSV
        if not os.path.exists(target_path):
            print(f"[!] Combined dataset not found at {target_path}. Falling back to {DEFAULT_LOCAL_CSV}")
            target_path = DEFAULT_LOCAL_CSV
        print(f"[*] Reading combined training dataset from {target_path}...")
        df = pd.read_csv(target_path)
        print(f"[+] Loaded {len(df):,} rows from {target_path}.")

    elif source_type == 'tn':
        target_path = dataset_arg or DEFAULT_TN_CSV
        print(f"[*] Reading Tamil Nadu State Board sample dataset from {target_path}...")
        df = pd.read_csv(target_path)
        print(f"[+] Loaded {len(df):,} rows from {target_path}.")

    else:  # 'csv' or default local
        target_path = dataset_arg or DEFAULT_LOCAL_CSV
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Dataset file not found at: {target_path}")
        print(f"[*] Reading CSV file from {target_path}...")
        df = pd.read_csv(target_path)
        print(f"[+] Loaded {len(df):,} rows from {target_path}.")

    return df


def preprocess_data(df, task):
    """
    Validates columns, standardizes labels, cleans text, and removes duplicates.
    """
    log_step(f"Step 2: Preprocessing & Label Standardization for Task '{task.upper()}'")

    # Detect question text column
    question_col = None
    for candidate in ['question', 'question_text', 'text', 'Question', 'content']:
        if candidate in df.columns:
            question_col = candidate
            break
    if not question_col:
        raise ValueError(f"Could not identify question text column. Available: {df.columns.tolist()}")

    # Detect target column
    target_col = None
    if task == 'bloom':
        for candidate in ['bloom_level', 'bloom', 'bloom_taxonomy', 'cognitive_level', 'Bloom_Level']:
            if candidate in df.columns:
                target_col = candidate
                break
    else:  # difficulty
        for candidate in ['difficulty', 'difficulty_level', 'diff', 'Difficulty']:
            if candidate in df.columns:
                target_col = candidate
                break

    if not target_col:
        raise ValueError(f"Could not find label column for task '{task}'. Available: {df.columns.tolist()}")

    print(f"[*] Question column: '{question_col}' | Label column: '{target_col}'")

    # Clean text: drop nulls and convert to string
    clean_df = df.dropna(subset=[question_col, target_col]).copy()
    clean_df[question_col] = clean_df[question_col].astype(str).str.strip()
    clean_df = clean_df[clean_df[question_col].str.len() >= 5]

    # Normalize labels
    if task == 'bloom':
        def normalize_bloom(val):
            val_str = str(val).strip().lower()
            return BLOOM_NORMALIZATION_MAP.get(val_str, None)

        clean_df['normalized_label'] = clean_df[target_col].apply(normalize_bloom)
        valid_classes = BLOOM_CLASSES
    else:
        def normalize_diff(val):
            val_str = str(val).strip().lower()
            return DIFFICULTY_NORMALIZATION_MAP.get(val_str, None)

        clean_df['normalized_label'] = clean_df[target_col].apply(normalize_diff)
        valid_classes = DIFFICULTY_CLASSES

    # Drop unmapped or invalid labels
    before_count = len(clean_df)
    clean_df = clean_df.dropna(subset=['normalized_label'])
    clean_df = clean_df[clean_df['normalized_label'].isin(valid_classes)]
    dropped = before_count - len(clean_df)
    if dropped > 0:
        print(f"[*] Pruned {dropped:,} records with invalid/unrecognized labels.")

    # Deduplicate questions
    initial_valid = len(clean_df)
    clean_df = clean_df.drop_duplicates(subset=[question_col])
    dedup_dropped = initial_valid - len(clean_df)
    if dedup_dropped > 0:
        print(f"[*] Removed {dedup_dropped:,} exact duplicate questions.")

    print(f"[+] Final preprocessed samples: {len(clean_df):,}")
    print("[*] Class Distribution:")
    counts = clean_df['normalized_label'].value_counts()
    for cls in valid_classes:
        cnt = counts.get(cls, 0)
        pct = (cnt / len(clean_df) * 100) if len(clean_df) > 0 else 0
        print(f"    - {cls:12s}: {cnt:6,} ({pct:5.1f}%)")

    return clean_df, question_col, 'normalized_label', valid_classes


def train_and_evaluate_task(
    df,
    question_col,
    label_col,
    target_classes,
    task,
    n_estimators=100,
    max_features=10000,
    sample_limit=None,
    test_size=0.20,
    random_state=42,
    activate=False,
    source_name="dataset"
):
    """
    Executes stratified split, trains Random Forest pipeline, evaluates on held-out test data,
    saves versioned joblib artifacts and json reports.
    """
    log_step(f"Step 3: Training & Held-Out Evaluation ({task.upper()} CLASSIFIER)")

    # Sample limit if requested (e.g. for fast local iteration)
    if sample_limit and sample_limit < len(df):
        print(f"[*] Applying sample limit: {sample_limit:,} rows (stratified sample)")
        samples_per_class = max(10, int(sample_limit / len(target_classes)))
        sampled_dfs = []
        for cls in target_classes:
            cls_df = df[df[label_col] == cls]
            n_take = min(len(cls_df), samples_per_class)
            if n_take > 0:
                sampled_dfs.append(cls_df.sample(n=n_take, random_state=random_state))
        df = pd.concat(sampled_dfs, ignore_index=True).sample(frac=1.0, random_state=random_state).reset_index(drop=True)
        print(f"[+] Sampled {len(df):,} rows evenly across classes.")

    X = np.array([str(x) for x in df[question_col].tolist()], dtype=object)
    y = np.array([str(val) for val in df[label_col].tolist()], dtype=object)

    # Stratified 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state,
        stratify=y
    )

    print(f"[*] Train set: {len(X_train):,} samples | Held-out test set: {len(X_test):,} samples")

    # Majority baseline classifier
    baseline = DummyClassifier(strategy='most_frequent')
    baseline.fit(X_train, y_train)
    baseline_acc = float(accuracy_score(y_test, baseline.predict(X_test)))
    print(f"[*] Majority-class baseline test accuracy: {baseline_acc * 100:.2f}%")

    # Build Pipeline: TF-IDF + Random Forest Classifier
    print(f"[*] Fitting TfidfVectorizer (max_features={max_features}, ngrams=(1,2)) + RandomForestClassifier (n_estimators={n_estimators}, n_jobs=-1)...")
    t0 = time.time()

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=max_features,
            sublinear_tf=True,
            strip_accents='unicode',
            lowercase=True
        )),
        ('rf', RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,
            class_weight='balanced'
        ))
    ])

    pipeline.fit(X_train, y_train)
    train_duration = round(time.time() - t0, 2)
    print(f"[+] Training completed in {train_duration}s.")

    # Evaluation on held-out test split
    print(f"[*] Evaluating on {len(X_test):,} held-out test questions...")
    y_pred = pipeline.predict(X_test)

    acc = float(accuracy_score(y_test, y_pred))
    macro_prec = float(precision_score(y_test, y_pred, average='macro', zero_division=0))
    macro_rec = float(recall_score(y_test, y_pred, average='macro', zero_division=0))
    macro_f1 = float(f1_score(y_test, y_pred, average='macro', zero_division=0))
    weighted_f1 = float(f1_score(y_test, y_pred, average='weighted', zero_division=0))

    print("\n" + "-" * 70)
    print(f"  HELD-OUT TEST RESULTS: {task.upper()} CLASSIFIER")
    print("-" * 70)
    print(f"  Accuracy:         {acc * 100:.2f}%  (Baseline: {baseline_acc * 100:.2f}%)")
    print(f"  Macro Precision:  {macro_prec:.4f}")
    print(f"  Macro Recall:     {macro_rec:.4f}")
    print(f"  Macro F1-Score:   {macro_f1:.4f}")
    print(f"  Weighted F1:      {weighted_f1:.4f}")
    print("-" * 70)

    # Classification report
    clf_report = classification_report(
        y_test, y_pred, labels=target_classes, output_dict=True, zero_division=0
    )
    print("\nPer-Class Classification Report:")
    print(classification_report(y_test, y_pred, labels=target_classes, zero_division=0))

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred, labels=target_classes)
    print("Confusion Matrix:")
    header = "          " + "".join([f"{cls[:6]:>8}" for cls in target_classes])
    print(header)
    for i, cls in enumerate(target_classes):
        row = f"{cls[:8]:<10}" + "".join([f"{cm[i][j]:>8}" for j in range(len(target_classes))])
        print(row)

    # Save artifacts
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    version_str = f"rf-{task}-local-v{timestamp}"
    versioned_model_path = os.path.join(MODELS_DIR, f"{version_str}.joblib")
    joblib.dump(pipeline, versioned_model_path)
    file_size_mb = round(os.path.getsize(versioned_model_path) / (1024 * 1024), 2)
    print(f"\n[+] Saved versioned model artifact: {versioned_model_path} ({file_size_mb} MB)")

    # Save JSON evaluation report
    report_data = {
        'model_version': version_str,
        'task_name': f"{task}_level" if task == 'bloom' else 'difficulty',
        'algorithm': 'RandomForestClassifier',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'dataset_source': source_name,
        'hyperparameters': {
            'n_estimators': n_estimators,
            'max_features': max_features,
            'ngram_range': [1, 2],
            'sublinear_tf': True,
            'class_weight': 'balanced',
            'random_state': random_state
        },
        'dataset_split': {
            'total_samples': len(df),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'test_size': test_size
        },
        'metrics': {
            'accuracy': acc,
            'macro_precision': macro_prec,
            'macro_recall': macro_rec,
            'macro_f1': macro_f1,
            'weighted_f1': weighted_f1,
            'majority_baseline_accuracy': baseline_acc
        },
        'classification_report': clf_report,
        'confusion_matrix': {
            'labels': target_classes,
            'matrix': cm.tolist()
        },
        'training_duration_seconds': train_duration,
        'artifact_path': versioned_model_path
    }

    report_path = os.path.join(REPORTS_DIR, f"{task}_local_evaluation.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2)
    print(f"[+] Saved evaluation report to: {report_path}")

    # Optional Production Activation
    if activate:
        prod_filename = f"{task}_model.joblib"
        prod_model_path = os.path.join(MODELS_DIR, prod_filename)
        joblib.dump(pipeline, prod_model_path)
        print(f"[+] ACTIVATED MODEL: Copied to active production path: {prod_model_path}")

        # Update database ModelVersion record if database is accessible
        try:
            from database.db import SessionLocal
            from database.models import ModelVersion
            db = SessionLocal()
            try:
                task_field = f"{task}_level" if task == 'bloom' else 'difficulty'
                # Deactivate current active models for this task
                db.query(ModelVersion).filter_by(task_name=task_field).update({'is_active': False})
                # Register new active version
                new_version = ModelVersion(
                    version=version_str,
                    task_name=task_field,
                    algorithm='RandomForestClassifier',
                    model_path=versioned_model_path,
                    accuracy=acc,
                    macro_f1=macro_f1,
                    weighted_f1=weighted_f1,
                    is_active=True,
                    classes_list=target_classes,
                    total_samples=len(df),
                    metrics_json=json.dumps(report_data['metrics'])
                )
                db.add(new_version)
                db.commit()
                print(f"[+] Registered active model in database ModelVersion table.")
            finally:
                db.close()
        except Exception as db_err:
            print(f"[!] Note: Database model registry update skipped ({db_err}). Model file is active.")

    return report_data


def main():
    parser = argparse.ArgumentParser(
        description="ExamForge AI - Local Random Forest Model Training CLI (VS Code Workflow)"
    )
    parser.add_argument(
        '--task',
        choices=['bloom', 'difficulty', 'all'],
        default='all',
        help="Classification task to train (default: 'all')"
    )
    parser.add_argument(
        '--source',
        choices=['csv', 'hf', 'combined', 'tn'],
        default='csv',
        help="Dataset source: 'csv' (default), 'hf' (Hugging Face), 'combined', or 'tn' (State Board)"
    )
    parser.add_argument(
        '--dataset',
        type=str,
        default=None,
        help="Custom CSV file path or Hugging Face dataset name"
    )
    parser.add_argument(
        '--download-hf',
        action='store_true',
        help="Force direct download from Hugging Face dataset 'Uzaib52/edubloom-question-bank'"
    )
    parser.add_argument(
        '--sample-limit',
        type=int,
        default=None,
        help="Optional max number of rows to train on (e.g. 10000 for fast testing)"
    )
    parser.add_argument(
        '--n-estimators',
        type=int,
        default=100,
        help="Number of trees in Random Forest (default: 100)"
    )
    parser.add_argument(
        '--max-features',
        type=int,
        default=10000,
        help="Maximum TF-IDF n-gram vocabulary features (default: 10000)"
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.20,
        help="Held-out test split ratio (default: 0.20)"
    )
    parser.add_argument(
        '--random-state',
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        '--activate',
        action='store_true',
        help="Promote and activate the newly trained model as the active production model"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("      EXAMFORGE AI - LOCAL MACHINE LEARNING TRAINING CLI")
    print("  Tamil Nadu State Board & EduBloom Question Classification")
    print("=" * 70)
    print(f"  Task:          {args.task.upper()}")
    print(f"  Source:        {args.source.upper()}")
    print(f"  Dataset:       {args.dataset or 'Default for source'}")
    print(f"  Trees (RF):    {args.n_estimators}")
    print(f"  Max Features:  {args.max_features}")
    print(f"  Sample Limit:  {args.sample_limit or 'None (Full Dataset)'}")
    print(f"  Held-out Test: {args.test_size * 100:.0f}%")
    print(f"  Activate Prod: {args.activate}")
    print("=" * 70)

    # 1. Load dataset
    raw_df = load_dataset_source(
        source_type=args.source,
        dataset_arg=args.dataset,
        download_hf=args.download_hf
    )

    tasks_to_run = ['bloom', 'difficulty'] if args.task == 'all' else [args.task]

    reports = {}
    for t in tasks_to_run:
        clean_df, q_col, l_col, classes = preprocess_data(raw_df, task=t)
        report = train_and_evaluate_task(
            df=clean_df,
            question_col=q_col,
            label_col=l_col,
            target_classes=classes,
            task=t,
            n_estimators=args.n_estimators,
            max_features=args.max_features,
            sample_limit=args.sample_limit,
            test_size=args.test_size,
            random_state=args.random_state,
            activate=args.activate,
            source_name=args.dataset or args.source
        )
        reports[t] = report

    log_step("TRAINING SUMMARY & ARTIFACT STATUS")
    for t, rep in reports.items():
        print(f"[*] Task '{t.upper()}':")
        print(f"    - Accuracy:        {rep['metrics']['accuracy'] * 100:.2f}%")
        print(f"    - Macro F1:        {rep['metrics']['macro_f1']:.4f}")
        print(f"    - Model Artifact:  {rep['artifact_path']}")
    print(f"\n[+] Local ML Training Completed Successfully.")


if __name__ == '__main__':
    main()
