"""
Text preprocessing utilities for ML pipeline.
"""

import re
import string


def normalize_text(text):
    """
    Lightweight text normalization for question classification.
    - Lowercase
    - Remove special characters but keep alphanumeric, spaces, and common punctuation
    - Collapse multiple spaces
    - Strip leading/trailing whitespace
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    
    text = text.lower()
    # Remove HTML tags if any
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', ' ', text)
    # Keep letters, numbers, spaces, and basic punctuation
    text = re.sub(r'[^a-z0-9\s\.\?\!\,\;\:\-]', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def validate_question_text(text):
    """
    Validate that question text is suitable for classification.
    Returns (is_valid, message).
    """
    if not isinstance(text, str):
        return False, "Input must be a string"
    
    text = text.strip()
    if len(text) == 0:
        return False, "Question text is empty"
    
    if len(text) < 5:
        return False, "Question text is too short (minimum 5 characters)"
    
    if len(text) > 10000:
        return False, "Question text is too long (maximum 10000 characters)"
    
    return True, "Valid"
