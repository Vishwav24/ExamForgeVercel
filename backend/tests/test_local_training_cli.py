"""Safe tests for local candidate training and application-compatible inference."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import Config
from ml.predict import ModelPredictor
from ml.train_local import preprocess_data, train_and_evaluate_task


class TestLocalTrainingCli(unittest.TestCase):
    def test_candidate_models_are_timestamped_and_work_with_application_inference(self):
        bloom_labels = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
        difficulty_labels = ['Easy', 'Medium', 'Hard']
        rows = []
        for index in range(30):
            rows.append({
                'question': f'Explain concept token{index} and provide an example.',
                'bloom_level': bloom_labels[index // 5],
                'difficulty': difficulty_labels[index % len(difficulty_labels)]
            })
        dataset = pd.DataFrame(rows)

        with tempfile.TemporaryDirectory() as output_dir:
            models_dir = os.path.join(output_dir, 'models')
            reports_dir = os.path.join(output_dir, 'reports')
            reports = {}

            with patch('ml.train_local.MODELS_DIR', models_dir), \
                    patch('ml.train_local.REPORTS_DIR', reports_dir):
                for task in ('bloom', 'difficulty'):
                    clean_df, question_col, label_col, classes = preprocess_data(dataset, task)
                    reports[task] = train_and_evaluate_task(
                        df=clean_df,
                        question_col=question_col,
                        label_col=label_col,
                        target_classes=classes,
                        task=task,
                        n_estimators=5,
                        max_features=128,
                        test_size=0.20,
                        random_state=42,
                        source_name='test fixture'
                    )

            bloom_report = reports['bloom']
            difficulty_report = reports['difficulty']
            self.assertTrue(bloom_report['candidate'])
            self.assertTrue(difficulty_report['candidate'])
            self.assertIn('candidate-local-v', bloom_report['model_version'])
            self.assertIn('candidate-local-v', difficulty_report['model_version'])
            self.assertNotEqual(bloom_report['report_path'], difficulty_report['report_path'])
            self.assertTrue(os.path.isfile(bloom_report['artifact_path']))
            self.assertTrue(os.path.isfile(difficulty_report['artifact_path']))
            self.assertTrue(os.path.isfile(bloom_report['report_path']))
            self.assertTrue(os.path.isfile(difficulty_report['report_path']))
            self.assertTrue(bloom_report['candidate_verification']['saved_artifact_reloaded'])
            self.assertTrue(difficulty_report['candidate_verification']['saved_artifact_reloaded'])
            self.assertEqual(
                bloom_report['dataset_split']['train_samples']
                + bloom_report['dataset_split']['test_samples'],
                30
            )

            with patch.object(Config, 'BLOOM_MODEL_PATH', bloom_report['artifact_path']), \
                    patch.object(Config, 'DIFFICULTY_MODEL_PATH', difficulty_report['artifact_path']):
                predictor = ModelPredictor()
                bloom_result = predictor.predict_bloom(
                    'Explain a concept and provide an example from science.'
                )
                difficulty_result = predictor.predict_difficulty(
                    'Explain a concept and provide an example from science.'
                )

            self.assertIsNone(bloom_result.get('error'))
            self.assertIn(bloom_result['prediction'], bloom_labels)
            self.assertIn('probabilities', bloom_result)
            self.assertIsNone(difficulty_result.get('error'))
            self.assertIn(difficulty_result['prediction'], difficulty_labels)
            self.assertIn('probabilities', difficulty_result)


if __name__ == '__main__':
    unittest.main()
