"""
EduBloom Dataset Ingestion, Inspection, and Cleaning Pipeline
Downloads 'Uzaib52/edubloom-question-bank' from Hugging Face, validates the schema,
removes missing and duplicate records, normalizes Bloom and difficulty labels,
and exports cleaned CSV and data quality metrics.

Target Dataset: Uzaib52/edubloom-question-bank (MIT License)
Output Dataset: backend/data/questions_dataset.csv
Output Report:  backend/reports/data_quality.json
"""

import os
import sys
import json
import argparse
import pandas as pd
import numpy as np

# Resolve project base directory relative to this script file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

OUTPUT_CSV_PATH = os.path.join(DATA_DIR, 'questions_dataset.csv')
DATA_QUALITY_JSON_PATH = os.path.join(REPORTS_DIR, 'data_quality.json')

# Standard target Bloom taxonomy levels
VALID_BLOOM_LEVELS = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']

# Standard target difficulty levels
VALID_DIFFICULTY_LEVELS = ['Easy', 'Medium', 'Hard']

# Source label normalization dictionaries (strictly mapping supported labels without invention)
BLOOM_MAPPINGS = {
    'l1': 'Remember',
    'l2': 'Understand',
    'l3': 'Apply',
    'l4': 'Analyze',
    'l5': 'Evaluate',
    'l6': 'Create',
    'remember': 'Remember',
    'remembering': 'Remember',
    'recall': 'Remember',
    'knowledge': 'Remember',
    'understand': 'Understand',
    'understanding': 'Understand',
    'comprehension': 'Understand',
    'comprehend': 'Understand',
    'apply': 'Apply',
    'applying': 'Apply',
    'application': 'Apply',
    'analyze': 'Analyze',
    'analyse': 'Analyze',
    'analyzing': 'Analyze',
    'analysing': 'Analyze',
    'analysis': 'Analyze',
    'evaluate': 'Evaluate',
    'evaluating': 'Evaluate',
    'evaluation': 'Evaluate',
    'create': 'Create',
    'creating': 'Create',
    'creation': 'Create',
    'synthesis': 'Create',
    'synthesize': 'Create',
}

DIFFICULTY_MAPPINGS = {
    'easy': 'Easy',
    'simple': 'Easy',
    'basic': 'Easy',
    'low': 'Easy',
    'medium': 'Medium',
    'moderate': 'Medium',
    'intermediate': 'Medium',
    'hard': 'Hard',
    'difficult': 'Hard',
    'advanced': 'Hard',
    'high': 'Hard',
}


def ensure_directories():
    """Ensure output directories exist relative to the project structure."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


def download_huggingface_dataset(dataset_name="Uzaib52/edubloom-question-bank"):
    """
    Download dataset programmatically using the Hugging Face datasets library.
    Falls back to direct URL resolution if the datasets cache fails.
    """
    print("=" * 65)
    print(f"STEP 1: Downloading dataset '{dataset_name}' from Hugging Face")
    print("=" * 65)

    try:
        from datasets import load_dataset
        ds = load_dataset(dataset_name)
        splits = list(ds.keys())
        print(f"Dataset successfully loaded. Available splits: {splits}")

        if 'train' in ds:
            df = ds['train'].to_pandas()
        else:
            first_split = splits[0]
            print(f"Using split '{first_split}'")
            df = ds[first_split].to_pandas()

        print(f"Retrieved {len(df)} rows across {len(df.columns)} columns.")
        return df

    except Exception as e:
        print(f"Hugging Face datasets library error: {e}")
        print("Attempting direct CSV download from Hugging Face repository...")
        try:
            url = f"https://huggingface.co/datasets/{dataset_name}/resolve/main/questions.csv"
            df = pd.read_csv(url)
            print(f"Direct download succeeded with {len(df)} records.")
            return df
        except Exception as e2:
            raise RuntimeError(
                f"Failed to retrieve dataset programmatically:\nDatasets error: {e}\nDirect download error: {e2}\n"
                f"Ensure internet connectivity or check dataset access: https://huggingface.co/datasets/{dataset_name}"
            )


def inspect_schema_and_columns(df):
    """
    Inspect the raw dataset schema, identify relevant columns, and display samples.
    """
    print("\n" + "=" * 65)
    print("STEP 2: Inspecting Dataset Schema, Columns, and Sample Records")
    print("=" * 65)

    columns = list(df.columns)
    print(f"Total Rows:    {len(df)}")
    print(f"Total Columns: {len(columns)}")
    print(f"Actual Columns: {columns}")

    # Identify relevant columns dynamically
    col_mapping = {}

    # Question text column
    for col in ['question', 'question_text', 'prompt', 'text', 'query']:
        if col in df.columns:
            col_mapping['question'] = col
            break

    # Bloom taxonomy column
    for col in ['bloom_level', 'bloom', 'bloom_taxonomy', 'taxonomy', 'cognitive_level']:
        if col in df.columns:
            col_mapping['bloom_level'] = col
            break

    # Difficulty column
    for col in ['difficulty', 'difficulty_level', 'level']:
        if col in df.columns:
            col_mapping['difficulty'] = col
            break

    # Additional metadata columns
    for meta in ['question_id', 'id', 'subject', 'topic', 'question_type', 'type', 'marks']:
        if meta in df.columns:
            col_mapping[meta] = meta

    print(f"Identified Column Roles: {col_mapping}")

    if 'question' not in col_mapping:
        raise ValueError(f"Could not identify question text column in available columns: {columns}")
    if 'bloom_level' not in col_mapping:
        raise ValueError(f"Could not identify Bloom's Taxonomy column in available columns: {columns}")
    if 'difficulty' not in col_mapping:
        raise ValueError(f"Could not identify Difficulty column in available columns: {columns}")

    # Missing values check
    missing_dict = {}
    print("\nMissing Values by Column:")
    for col in columns:
        missing_count = int(df[col].isna().sum())
        pct = (missing_count / len(df)) * 100 if len(df) > 0 else 0
        missing_dict[col] = missing_count
        print(f"  - {col}: {missing_count} missing ({pct:.2f}%)")

    # Display sample records
    print("\nSample Records (First 2):")
    sample_records = df.head(2).to_dict(orient='records')
    for idx, rec in enumerate(sample_records, 1):
        print(f"  Record {idx}: {rec}")

    return col_mapping, missing_dict


def clean_and_normalize(df, col_mapping):
    """
    Clean the dataset:
    - Standardize column names
    - Remove rows with missing question text or target labels
    - Remove exact duplicate questions while preserving metadata
    - Normalize Bloom labels to the 6 standard levels
    - Normalize Difficulty labels to Easy, Medium, Hard
    """
    print("\n" + "=" * 65)
    print("STEP 3: Cleaning & Label Normalization")
    print("=" * 65)

    original_row_count = len(df)
    clean_df = df.copy()

    # Standardize column names according to identified mapping
    inverse_map = {v: k for k, v in col_mapping.items() if k in ['question', 'bloom_level', 'difficulty']}
    clean_df = clean_df.rename(columns=inverse_map)

    # 1. Clean strings and strip whitespace
    for col in clean_df.columns:
        if clean_df[col].dtype == object or str(clean_df[col].dtype).startswith('string'):
            clean_df[col] = clean_df[col].astype(str).str.strip()
            clean_df.loc[clean_df[col].isin(['nan', 'None', '', 'NaN', 'null']), col] = np.nan

    # 2. Remove missing question text
    before_q = len(clean_df)
    clean_df = clean_df.dropna(subset=['question'])
    removed_missing_questions = before_q - len(clean_df)
    print(f"Removed {removed_missing_questions} rows with missing question text.")

    # 3. Remove missing target labels
    before_b = len(clean_df)
    clean_df = clean_df.dropna(subset=['bloom_level'])
    removed_missing_bloom = before_b - len(clean_df)
    print(f"Removed {removed_missing_bloom} rows with missing bloom_level.")

    before_d = len(clean_df)
    clean_df = clean_df.dropna(subset=['difficulty'])
    removed_missing_diff = before_d - len(clean_df)
    print(f"Removed {removed_missing_diff} rows with missing difficulty.")

    # 4. Normalize Bloom labels
    raw_bloom_counts = clean_df['bloom_level'].value_counts().to_dict()
    clean_df['bloom_level'] = clean_df['bloom_level'].astype(str).str.lower().map(BLOOM_MAPPINGS)

    # Filter out unsupported/unmapped Bloom labels without fabricating
    before_bloom_filter = len(clean_df)
    clean_df = clean_df[clean_df['bloom_level'].isin(VALID_BLOOM_LEVELS)]
    unmapped_bloom_removed = before_bloom_filter - len(clean_df)
    if unmapped_bloom_removed > 0:
        print(f"Removed {unmapped_bloom_removed} rows with unsupported Bloom labels.")

    # 5. Normalize Difficulty labels
    raw_diff_counts = clean_df['difficulty'].value_counts().to_dict()
    clean_df['difficulty'] = clean_df['difficulty'].astype(str).str.lower().map(DIFFICULTY_MAPPINGS)

    # Filter out unsupported/unmapped difficulty labels without fabricating
    before_diff_filter = len(clean_df)
    clean_df = clean_df[clean_df['difficulty'].isin(VALID_DIFFICULTY_LEVELS)]
    unmapped_diff_removed = before_diff_filter - len(clean_df)
    if unmapped_diff_removed > 0:
        print(f"Removed {unmapped_diff_removed} rows with unsupported Difficulty labels.")

    # 6. Remove exact duplicate questions while keeping metadata
    before_dups = len(clean_df)
    clean_df = clean_df.drop_duplicates(subset=['question'], keep='first')
    duplicates_removed = before_dups - len(clean_df)
    print(f"Removed {duplicates_removed} exact duplicate questions.")

    final_row_count = len(clean_df)
    print(f"\nFinal Cleaned Rows: {final_row_count} (Retained {final_row_count / original_row_count * 100:.2f}% of raw data)")

    # Compute final distributions
    final_bloom_dist = {k: int(v) for k, v in clean_df['bloom_level'].value_counts().items()}
    final_diff_dist = {k: int(v) for k, v in clean_df['difficulty'].value_counts().items()}

    print("\nNormalized Bloom's Taxonomy Distribution:")
    for b_level in VALID_BLOOM_LEVELS:
        cnt = final_bloom_dist.get(b_level, 0)
        pct = (cnt / final_row_count) * 100 if final_row_count > 0 else 0
        print(f"  - {b_level}: {cnt} ({pct:.1f}%)")

    print("\nNormalized Difficulty Distribution:")
    for d_level in VALID_DIFFICULTY_LEVELS:
        cnt = final_diff_dist.get(d_level, 0)
        pct = (cnt / final_row_count) * 100 if final_row_count > 0 else 0
        print(f"  - {d_level}: {cnt} ({pct:.1f}%)")

    cleaning_stats = {
        'original_row_count': int(original_row_count),
        'cleaned_row_count': int(final_row_count),
        'removed_missing_questions': int(removed_missing_questions),
        'removed_missing_bloom': int(removed_missing_bloom),
        'removed_missing_difficulty': int(removed_missing_diff),
        'unmapped_bloom_removed': int(unmapped_bloom_removed),
        'unmapped_diff_removed': int(unmapped_diff_removed),
        'duplicates_removed': int(duplicates_removed),
        'raw_bloom_distribution': {str(k): int(v) for k, v in raw_bloom_counts.items()},
        'raw_difficulty_distribution': {str(k): int(v) for k, v in raw_diff_counts.items()},
        'final_bloom_distribution': final_bloom_dist,
        'final_difficulty_distribution': final_diff_dist,
    }

    return clean_df, cleaning_stats


def save_dataset_and_report(df, cleaning_stats, missing_dict, raw_columns):
    """
    Save the cleaned dataframe to backend/data/questions_dataset.csv
    and quality metrics to backend/reports/data_quality.json.
    """
    print("\n" + "=" * 65)
    print("STEP 4: Saving Prepared Dataset and Quality Report")
    print("=" * 65)

    ensure_directories()

    # 1. Export Cleaned CSV
    df.to_csv(OUTPUT_CSV_PATH, index=False)
    print(f"✓ Saved cleaned dataset to: {OUTPUT_CSV_PATH}")
    print(f"  Dimensions: {df.shape[0]} rows × {df.shape[1]} columns")

    # 2. Build and Export JSON Quality Report
    quality_report = {
        'dataset_source': 'Uzaib52/edubloom-question-bank',
        'license': 'MIT',
        'actual_columns': raw_columns,
        'missing_values': missing_dict,
        'original_row_count': cleaning_stats['original_row_count'],
        'cleaned_row_count': cleaning_stats['cleaned_row_count'],
        'duplicates_removed': cleaning_stats['duplicates_removed'],
        'removed_missing_questions': cleaning_stats['removed_missing_questions'],
        'removed_missing_bloom': cleaning_stats['removed_missing_bloom'],
        'removed_missing_difficulty': cleaning_stats['removed_missing_difficulty'],
        'raw_bloom_distribution': cleaning_stats['raw_bloom_distribution'],
        'raw_difficulty_distribution': cleaning_stats['raw_difficulty_distribution'],
        'label_distributions': {
            'bloom_level': cleaning_stats['final_bloom_distribution'],
            'difficulty': cleaning_stats['final_difficulty_distribution']
        }
    }

    with open(DATA_QUALITY_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(quality_report, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved data quality report to: {DATA_QUALITY_JSON_PATH}")

    # Also maintain data_quality_report.json for existing backend endpoints
    alt_report_path = os.path.join(REPORTS_DIR, 'data_quality_report.json')
    with open(alt_report_path, 'w', encoding='utf-8') as f:
        json.dump(quality_report, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Download and prepare EduBloom question bank dataset.")
    parser.add_argument('--force', action='store_true', help='Force re-download even if CSV already exists.')
    args = parser.parse_args()

    ensure_directories()

    # Download
    df_raw = download_huggingface_dataset()

    # Inspect
    col_mapping, missing_dict = inspect_schema_and_columns(df_raw)

    # Clean & Normalize
    df_cleaned, cleaning_stats = clean_and_normalize(df_raw, col_mapping)

    # Save
    save_dataset_and_report(df_cleaned, cleaning_stats, missing_dict, list(df_raw.columns))

    print("\n" + "=" * 65)
    print("ETL PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 65)


if __name__ == '__main__':
    main()
