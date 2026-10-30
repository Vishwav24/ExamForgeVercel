#!/usr/bin/env python3
"""
ExamForge AI - Root Local ML Training Runner for VS Code
Direct shortcut to backend/ml/train_local.py.

Usage:
  python train_local.py --task bloom
  python train_local.py --task difficulty
  python train_local.py --task all --sample-limit 10000
  python train_local.py --source hf
"""

import sys
import os

# Set working directory to project root and delegate to backend.ml.train_local
root_dir = os.path.abspath(os.path.dirname(__file__))
backend_dir = os.path.join(root_dir, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.ml.train_local import main

if __name__ == '__main__':
    main()
