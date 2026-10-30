"""
Model Inference Module
Loads trained pipelines and provides prediction functions.
"""

import os
import sys
import joblib
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config
from ml.preprocessing import normalize_text, validate_question_text


class ModelPredictor:
    """Handles loading and inference for both trained models."""
    
    def __init__(self):
        self._bloom_model = None
        self._difficulty_model = None
        self._bloom_loaded = False
        self._difficulty_loaded = False
    
    def _load_bloom_model(self):
        """Load Bloom's Taxonomy classifier."""
        if self._bloom_loaded:
            return
        
        path = Config.BLOOM_MODEL_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Bloom model not found at {path}. Run ml/train_models.py first."
            )
        self._bloom_model = joblib.load(path)
        self._bloom_loaded = True
    
    def _load_difficulty_model(self):
        """Load Difficulty classifier."""
        if self._difficulty_loaded:
            return
        
        path = Config.DIFFICULTY_MODEL_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Difficulty model not found at {path}. Run ml/train_models.py first."
            )
        self._difficulty_model = joblib.load(path)
        self._difficulty_loaded = True
    
    def get_models_status(self):
        """Check which models are available."""
        bloom_exists = os.path.exists(Config.BLOOM_MODEL_PATH)
        diff_exists = os.path.exists(Config.DIFFICULTY_MODEL_PATH)
        
        return {
            'bloom_model': {
                'available': bloom_exists,
                'path': Config.BLOOM_MODEL_PATH if bloom_exists else None,
                'loaded': self._bloom_loaded,
            },
            'difficulty_model': {
                'available': diff_exists,
                'path': Config.DIFFICULTY_MODEL_PATH if diff_exists else None,
                'loaded': self._difficulty_loaded,
            },
            'both_ready': bloom_exists and diff_exists,
        }
    
    def reload_models(self):
        """Forces reloading of models from disk when a new version is activated."""
        self._bloom_model = None
        self._difficulty_model = None
        self._bloom_loaded = False
        self._difficulty_loaded = False
        print("ModelPredictor cache cleared; models will be reloaded on next inference.")
    
    def predict_bloom(self, question_text):
        """
        Predict Bloom's Taxonomy level for a question.
        Returns dict with prediction and confidence.
        """
        is_valid, msg = validate_question_text(question_text)
        if not is_valid:
            return {'error': msg, 'prediction': None, 'confidence': None}
        
        try:
            self._load_bloom_model()
        except FileNotFoundError as e:
            return {'error': str(e), 'prediction': None, 'confidence': None}
        
        processed = normalize_text(question_text)
        if not processed:
            return {'error': 'Question text could not be processed', 'prediction': None, 'confidence': None}
        
        prediction = self._bloom_model.predict([processed])[0]
        probabilities = self._bloom_model.predict_proba([processed])[0]
        classes = self._bloom_model.classes_.tolist()
        confidence = float(max(probabilities))
        
        prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, probabilities)}
        
        return {
            'prediction': prediction,
            'confidence': round(confidence, 4),
            'probabilities': prob_dict,
            'note': 'Confidence is a probability estimate, not a guarantee of correctness.'
        }
    
    def predict_difficulty(self, question_text):
        """
        Predict difficulty level for a question.
        Returns dict with prediction and confidence.
        """
        is_valid, msg = validate_question_text(question_text)
        if not is_valid:
            return {'error': msg, 'prediction': None, 'confidence': None}
        
        try:
            self._load_difficulty_model()
        except FileNotFoundError as e:
            return {'error': str(e), 'prediction': None, 'confidence': None}
        
        processed = normalize_text(question_text)
        if not processed:
            return {'error': 'Question text could not be processed', 'prediction': None, 'confidence': None}
        
        prediction = self._difficulty_model.predict([processed])[0]
        probabilities = self._difficulty_model.predict_proba([processed])[0]
        classes = self._difficulty_model.classes_.tolist()
        confidence = float(max(probabilities))
        
        prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, probabilities)}
        
        return {
            'prediction': prediction,
            'confidence': round(confidence, 4),
            'probabilities': prob_dict,
            'note': 'Confidence is a probability estimate, not a guarantee of correctness.'
        }
    
    def classify_question(self, question_text):
        """
        Full classification: both Bloom level and Difficulty.
        """
        bloom_result = self.predict_bloom(question_text)
        diff_result = self.predict_difficulty(question_text)
        
        return {
            'question': question_text[:200],  # Truncate for response
            'bloom': bloom_result,
            'difficulty': diff_result,
        }


# Singleton instance for the application
predictor = ModelPredictor()
