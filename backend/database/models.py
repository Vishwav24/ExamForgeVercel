"""
Database Models for ExamForge AI — Tamil Nadu State Board (Classes 6–12)
"""

import os
import sys
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import relationship

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import Base


class User(Base):
    """User account for administrator and teacher authentication."""
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='teacher')  # 'admin' or 'teacher'
    subject_specialization = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def assigned_subjects(self):
        """Return list of assigned subjects parsed safely from subject_specialization."""
        if not self.subject_specialization:
            return []
        raw = str(self.subject_specialization).strip()
        if not raw:
            return []
        if raw.startswith('[') and raw.endswith(']'):
            try:
                import json
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(s).strip() for s in parsed if str(s).strip()]
            except Exception:
                pass
        return [s.strip() for s in raw.split(',') if s.strip()]

    def to_dict(self):
        """Safe dictionary representation — never return password hash."""
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'subject_specialization': self.subject_specialization,
            'assigned_subjects': self.assigned_subjects,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Curriculum(Base):
    """Verified curriculum metadata for Tamil Nadu State Board (Samacheer Kalvi)."""
    __tablename__ = 'curriculum'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    board = Column(String(100), default='Tamil Nadu State Board', nullable=False)
    class_grade = Column(String(50), nullable=False)  # 'Class 6' to 'Class 12'
    subject = Column(String(100), nullable=False)
    chapter_number = Column(Integer, nullable=True)
    chapter_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'board': self.board,
            'class_grade': self.class_grade,
            'subject': self.subject,
            'chapter_number': self.chapter_number,
            'chapter_name': self.chapter_name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DatasetUpload(Base):
    """Record of CSV question paper datasets uploaded by Administrator."""
    __tablename__ = 'dataset_uploads'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    board = Column(String(100), default='Tamil Nadu State Board')
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    total_rows = Column(Integer, default=0)
    valid_rows = Column(Integer, default=0)
    invalid_rows = Column(Integer, default=0)
    duplicate_rows = Column(Integer, default=0)
    classes_covered = Column(JSON, nullable=True)  # List of classes found in dataset
    subjects_covered = Column(JSON, nullable=True)  # List of subjects found in dataset
    validation_report = Column(JSON, nullable=True)
    status = Column(String(50), default='uploaded')  # 'uploaded', 'validated', 'ready_for_training', 'trained', 'rejected'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'board': self.board,
            'uploaded_by': self.uploaded_by,
            'total_rows': self.total_rows,
            'valid_rows': self.valid_rows,
            'invalid_rows': self.invalid_rows,
            'duplicate_rows': self.duplicate_rows,
            'classes_covered': self.classes_covered or [],
            'subjects_covered': self.subjects_covered or [],
            'validation_report': self.validation_report or {},
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ModelVersion(Base):
    """Model training runs, versioning, and evaluation metrics."""
    __tablename__ = 'model_versions'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(50), nullable=False)  # 'bloom_level' or 'difficulty'
    algorithm = Column(String(100), default='RandomForestClassifier')
    version = Column(String(50), nullable=False)  # e.g., 'rf-bloom-v1.0'
    model_filename = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=False)
    dataset_upload_id = Column(Integer, ForeignKey('dataset_uploads.id'), nullable=True)
    dataset_name = Column(String(255), nullable=True)
    training_sample_count = Column(Integer, default=0)
    test_sample_count = Column(Integer, default=0)
    accuracy = Column(Float, nullable=True)
    macro_precision = Column(Float, nullable=True)
    macro_recall = Column(Float, nullable=True)
    macro_f1 = Column(Float, nullable=True)
    weighted_f1 = Column(Float, nullable=True)
    baseline_accuracy = Column(Float, nullable=True)
    baseline_macro_f1 = Column(Float, nullable=True)
    evaluation_metrics = Column(JSON, nullable=True)  # confusion matrix, per-class, etc.
    trained_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    training_duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'task_name': self.task_name,
            'algorithm': self.algorithm,
            'version': self.version,
            'model_filename': self.model_filename,
            'is_active': self.is_active,
            'dataset_upload_id': self.dataset_upload_id,
            'dataset_name': self.dataset_name,
            'training_sample_count': self.training_sample_count,
            'test_sample_count': self.test_sample_count,
            'accuracy': self.accuracy,
            'macro_precision': self.macro_precision,
            'macro_recall': self.macro_recall,
            'macro_f1': self.macro_f1,
            'weighted_f1': self.weighted_f1,
            'baseline_accuracy': self.baseline_accuracy,
            'baseline_macro_f1': self.baseline_macro_f1,
            'evaluation_metrics': self.evaluation_metrics or {},
            'trained_by': self.trained_by,
            'training_duration_seconds': self.training_duration_seconds,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(Base):
    """Audit log for tracking administrative and model lifecycle actions."""
    __tablename__ = 'audit_logs'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_email': self.user_email,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'details': self.details or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Question(Base):
    """Question bank entry."""
    __tablename__ = 'questions'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(String(100), unique=True, nullable=True)  # Original ID from dataset
    question = Column(Text, nullable=False)
    subject = Column(String(100), nullable=True)
    topic = Column(String(200), nullable=True)  # Chapter / Topic
    board = Column(String(100), nullable=True, default='Tamil Nadu State Board')
    class_grade = Column(String(50), nullable=True)  # 'Class 6' to 'Class 12'
    question_type = Column(String(100), nullable=True)
    marks = Column(Float, nullable=True)
    bloom_level = Column(String(50), nullable=True)
    difficulty = Column(String(50), nullable=True)
    source = Column(String(200), nullable=True, default='Tamil Nadu State Board Question Bank')
    dataset_upload_id = Column(Integer, ForeignKey('dataset_uploads.id'), nullable=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'question': self.question,
            'subject': self.subject,
            'topic': self.topic,
            'board': self.board,
            'class_grade': self.class_grade,
            'question_type': self.question_type,
            'marks': self.marks,
            'bloom_level': self.bloom_level,
            'difficulty': self.difficulty,
            'source': self.source,
            'verified': self.verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class GeneratedPaper(Base):
    """Record of generated question papers."""
    __tablename__ = 'generated_papers'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    board = Column(String(100), nullable=True, default='Tamil Nadu State Board')
    class_grade = Column(String(50), nullable=True)
    subject = Column(String(100), nullable=True)
    topic = Column(String(200), nullable=True)
    total_marks = Column(Float, nullable=True)
    duration_minutes = Column(Integer, default=90)
    num_questions = Column(Integer, nullable=True)
    question_type = Column(String(100), nullable=True)
    bloom_level = Column(String(50), nullable=True)
    difficulty = Column(String(50), nullable=True)
    
    # Generated result
    questions_json = Column(JSON, nullable=True)  # List of selected question dicts
    sections_json = Column(JSON, nullable=True)  # List of section definitions with questions
    pdf_filename = Column(String(300), nullable=True)
    
    # Status
    status = Column(String(50), default='generated')  # 'generated', 'downloaded'
    generation_seed = Column(Integer, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'board': self.board,
            'class_grade': self.class_grade,
            'subject': self.subject,
            'topic': self.topic,
            'total_marks': self.total_marks,
            'duration_minutes': self.duration_minutes or 90,
            'num_questions': self.num_questions,
            'question_type': self.question_type,
            'bloom_level': self.bloom_level,
            'difficulty': self.difficulty,
            'questions_json': self.questions_json,
            'sections': self.sections_json,
            'pdf_filename': self.pdf_filename,
            'status': self.status,
            'created_by_user_id': self.created_by_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
