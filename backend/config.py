import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY', 'examforge-secure-dev-key-tn-2026')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    
    # Database URL resolution
    raw_db_url = os.environ.get('DATABASE_URL')
    if raw_db_url:
        if raw_db_url.startswith('sqlite:///') and not os.path.isabs(raw_db_url.replace('sqlite:///', '')):
            rel_path = raw_db_url.replace('sqlite:///', '')
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.normpath(os.path.join(BASE_DIR, rel_path))}'
        else:
            SQLALCHEMY_DATABASE_URI = raw_db_url
    else:
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "database", "examforge.db")}'
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CORS Configuration
    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',')
        if origin.strip()
    ]
    
    # Paths
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    MODELS_DIR = os.path.join(BASE_DIR, 'models')
    REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
    GENERATED_PAPERS_DIR = os.path.join(BASE_DIR, 'generated_papers')
    
    # Dataset
    DATASET_CSV = os.path.join(DATA_DIR, 'questions_dataset.csv')
    
    # Model files
    BLOOM_MODEL_PATH = os.path.join(MODELS_DIR, 'bloom_model.joblib')
    DIFFICULTY_MODEL_PATH = os.path.join(MODELS_DIR, 'difficulty_model.joblib')
    
    # Bloom's Taxonomy levels (ordered by cognitive complexity)
    BLOOM_LEVELS = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
    
    # Difficulty levels
    DIFFICULTY_LEVELS = ['Easy', 'Medium', 'Hard']
    
    # Ensure directories exist
    @staticmethod
    def init_dirs():
        for d in [Config.DATA_DIR, Config.MODELS_DIR, Config.REPORTS_DIR, Config.GENERATED_PAPERS_DIR]:
            os.makedirs(d, exist_ok=True)

Config.init_dirs()
