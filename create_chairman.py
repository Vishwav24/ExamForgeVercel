"""
ExamForge AI — CLI Tool: Create Initial Chairman Account (Root Shortcut)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from create_chairman import prompt_chairman_creation

if __name__ == '__main__':
    prompt_chairman_creation()

