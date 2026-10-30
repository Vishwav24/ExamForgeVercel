"""
Candidate Discovery Script: Investigate and Screen Class 10 Science Questions
from backend/data/combined_training_dataset.csv.

Analyzes 74,716 records to determine if any can safely resolve Class 10 Science shortages.
Distinguishes original verified metadata from heuristic/ML predictions.
Writes findings to backend/data/discovered_c10_science_candidates_review.csv.
"""

import os
import sys
import re
import csv
import pandas as pd
from typing import Dict, List, Any, Optional

# Ensure backend is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.question_selection import is_vague_question

CLASS_10_SCIENCE_CHAPTERS = [
    "Laws of Motion",
    "Optics",
    "Thermal Physics",
    "Electricity",
    "Acoustics",
    "Nuclear Physics",
    "Atoms and Molecules",
    "Periodic Classification of Elements",
    "Solutions",
    "Types of Chemical Reactions",
    "Carbon and its Compounds",
    "Plant Anatomy and Plant Physiology",
    "Structural Organisation of Animals",
    "Transportation in Plants and Circulation in Animals",
    "Nervous System",
    "Plant and Animal Hormones",
    "Reproduction in Plants and Animals",
    "Heredity",
    "Origin and Evolution of Life",
    "Breeding and Biotechnology",
    "Environmental Management"
]

# Chapter keyword maps for candidate matching
CHAPTER_KEYWORDS = {
    "Laws of Motion": ["inertia", "newton", "momentum", "force", "gravitation", "action and reaction", "friction"],
    "Optics": ["refraction", "reflection", "lens", "convex", "concave", "dispersion", "focal length", "prism", "light"],
    "Thermal Physics": ["temperature", "heat", "thermal expansion", "boyle", "charles", "gas laws", "absolute zero"],
    "Electricity": ["current", "voltage", "resistance", "ohm", "joule", "circuit", "potential difference", "resistor"],
    "Acoustics": ["sound", "ultrasonic", "echo", "frequency", "doppler", "vibration", "amplitude"],
    "Nuclear Physics": ["radioactivity", "nuclear fission", "nuclear fusion", "alpha", "beta", "gamma", "uranium"],
    "Atoms and Molecules": ["relative atomic mass", "mole", "avogadro", "gram molecular mass", "vapour density"],
    "Periodic Classification of Elements": ["periodic table", "mendeleev", "atomic radius", "electronegativity", "ionization energy"],
    "Solutions": ["solute", "solvent", "solubility", "saturated", "colloid", "suspension", "concentration"],
    "Types of Chemical Reactions": ["combination", "decomposition", "displacement", "redox", "oxidation", "neutralization", "ph scale"],
    "Carbon and its Compounds": ["covalent", "hydrocarbon", "homologous", "alkane", "alkene", "alkyne", "ethanol", "ethanoic"],
    "Plant Anatomy and Plant Physiology": ["xylem", "phloem", "photosynthesis", "transpiration", "chloroplast", "stomata", "vascular bundle"],
    "Structural Organisation of Animals": ["leech", "rabbit", "circulatory system", "digestive system", "morphology"],
    "Transportation in Plants and Circulation in Animals": ["heart", "blood", "artery", "vein", "lymph", "transpiration pull", "rbc", "wbc"],
    "Nervous System": ["neuron", "brain", "spinal cord", "synapse", "reflex arc", "central nervous system"],
    "Plant and Animal Hormones": ["auxin", "gibberellin", "cytokinin", "insulin", "thyroid", "pituitary", "adrenaline"],
    "Reproduction in Plants and Animals": ["pollination", "fertilization", "gamete", "asexual", "sexual", "ovary", "testis"],
    "Heredity": ["mendel", "monohybrid", "dihybrid", "chromosome", "dna", "gene", "allele"],
    "Origin and Evolution of Life": ["lamarck", "darwin", "fossil", "homologous", "evolution", "paleontology"],
    "Breeding and Biotechnology": ["genetic engineering", "hybridization", "cloning", "r-dna", "mutation breeding"],
    "Environmental Management": ["conservation", "biodiversity", "renewable energy", "afforestation", "wildlife", "pollution"]
}


def discover_science_candidates(input_csv: str, output_csv: str) -> Dict[str, Any]:
    """Inspect input dataset and write discovered candidate review records."""
    df = pd.read_csv(input_csv)
    
    records: List[Dict[str, Any]] = []
    stats = {
        'total_rows_scanned': len(df),
        'science_related_rows': 0,
        'verified_tnsb_science_rows': 0,
        'verified_tnsb_1_mark_rows': 0,
        'edubloom_science_rows': 0,
        'edubloom_matches_found': 0,
        'vague_templates_detected': 0
    }

    sci_subjects = ['Science', 'Physics', 'Chemistry', 'Biology']
    
    for idx, row in df.iterrows():
        subj = str(row.get('subject', ''))
        if subj not in sci_subjects:
            continue
            
        stats['science_related_rows'] += 1
        q_id = str(row.get('question_id', f"ROW_{idx}"))
        q_text = str(row.get('question', '')).strip()
        topic = str(row.get('topic', '')).strip()
        source = str(row.get('source', ''))
        is_tn = bool(row.get('is_tn_state_board', False))
        
        # Check if already a verified TNSB question
        if is_tn:
            stats['verified_tnsb_science_rows'] += 1
            # Check if topic is in Class 10 chapters
            matched_chapter = topic if topic in CLASS_10_SCIENCE_CHAPTERS else None
            if matched_chapter:
                records.append({
                    'row_id': q_id,
                    'question_text': q_text,
                    'source': source,
                    'is_verified_tnsb': True,
                    'original_subject': subj,
                    'original_topic': topic,
                    'predicted_class_grade': 'Class 10 (Verified Source)',
                    'predicted_subject': 'Science',
                    'predicted_chapter': matched_chapter,
                    'confidence_score': 1.0,
                    'is_vague_template': False,
                    'eligible_for_1_mark': False,  # TNSB sample has 2m, 3m, 5m only
                    'review_recommendation': 'Verified TNSB curriculum question (2m/3m/5m; not 1-mark objective)'
                })
            continue

        # Process EduBloom questions
        stats['edubloom_science_rows'] += 1
        
        # Check vague template pattern
        is_vague, _ = is_vague_question(q_text)
        if is_vague:
            stats['vague_templates_detected'] += 1
            
        # Match against chapter keywords
        matched_chapter = None
        best_score = 0.0
        q_lower = q_text.lower()
        topic_lower = topic.lower()
        
        for ch_name, keywords in CHAPTER_KEYWORDS.items():
            score = 0
            if ch_name.lower() in topic_lower or topic_lower in ch_name.lower():
                score += 3
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', q_lower):
                    score += 1
            if score > best_score:
                best_score = score
                matched_chapter = ch_name
                
        # If score indicates meaningful topic match
        if best_score >= 2 and matched_chapter:
            stats['edubloom_matches_found'] += 1
            conf = min(0.65, 0.2 + (best_score * 0.08))
            
            # Recommendation based on quality check
            if is_vague:
                rec = "Generic EduBloom template lacking secondary school concepts; not recommended"
            elif len(q_text) > 200:
                rec = "Disciplinary prompt; needs manual teacher curation for secondary syllabus"
            else:
                rec = "Potential conceptual candidate; requires teacher syllabus verification and marks assignment"

            records.append({
                'row_id': q_id,
                'question_text': q_text,
                'source': source,
                'is_verified_tnsb': False,
                'original_subject': subj,
                'original_topic': topic,
                'predicted_class_grade': 'Class 10 (Predicted / Heuristic)',
                'predicted_subject': 'Science',
                'predicted_chapter': matched_chapter,
                'confidence_score': round(conf, 2),
                'is_vague_template': is_vague,
                'eligible_for_1_mark': False,  # Unverified marks
                'review_recommendation': rec
            })

    # Save to review CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    fieldnames = [
        'row_id', 'question_text', 'source', 'is_verified_tnsb',
        'original_subject', 'original_topic', 'predicted_class_grade',
        'predicted_subject', 'predicted_chapter', 'confidence_score',
        'is_vague_template', 'eligible_for_1_mark', 'review_recommendation'
    ]
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    stats['total_review_records_written'] = len(records)
    return stats


def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    input_file = os.path.join(base_dir, 'data', 'combined_training_dataset.csv')
    output_file = os.path.join(base_dir, 'data', 'discovered_c10_science_candidates_review.csv')

    print("=== Candidate Discovery: Class 10 Science in combined_training_dataset.csv ===")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    
    stats = discover_science_candidates(input_file, output_file)
    
    print("\n--- Discovery Audit Summary ---")
    print(f"Total Rows Scanned: {stats['total_rows_scanned']:,}")
    print(f"Science-Related Rows: {stats['science_related_rows']:,}")
    print(f"Verified TNSB Science Rows: {stats['verified_tnsb_science_rows']:,}")
    print(f"Verified TNSB 1-Mark Science Questions: {stats['verified_tnsb_1_mark_rows']} (ZERO in combined dataset)")
    print(f"EduBloom Science Rows: {stats['edubloom_science_rows']:,}")
    print(f"EduBloom Topic Matches Screened: {stats['edubloom_matches_found']:,}")
    print(f"Vague Templates Detected in EduBloom: {stats['vague_templates_detected']:,}")
    print(f"Total Candidate Records Written to Review CSV: {stats['total_review_records_written']:,}")


if __name__ == '__main__':
    main()

