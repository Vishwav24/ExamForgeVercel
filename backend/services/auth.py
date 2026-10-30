"""
Authentication and Role-Based Access Control (RBAC) Utilities for ExamForge AI.
Handles password hashing, token encoding/decoding, role verification, and audit logging.
"""

import os
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database.db import SessionLocal
from database.models import User, AuditLog

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', Config.SECRET_KEY)
JWT_ALGORITHM = 'HS256'
TOKEN_EXPIRATION_HOURS = 24


def hash_password(password: str) -> str:
    """Hash password using Werkzeug's default pbkdf2:sha256."""
    return generate_password_hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify raw password against stored hash."""
    return check_password_hash(hashed_password, password)


def create_access_token(user: User) -> str:
    """Generate signed JWT token containing user identity, email, role, and expiration."""
    payload = {
        'sub': str(user.id),
        'email': user.email,
        'role': user.role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRATION_HOURS),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str):
    """Decode and validate JWT token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def auth_required(f):
    """
    Decorator to enforce authentication on protected endpoints.
    Accepts token via Authorization header: Bearer <token> or ?token= query parameter.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()
        elif request.args.get('token'):
            token = request.args.get('token').strip()
            
        if not token:
            return jsonify({'error': 'Authentication required. Missing or invalid Bearer token.'}), 401
        
        payload = decode_access_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired. Please log in again.'}), 401
        
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(id=int(payload['sub'])).first()
            if not user or not user.is_active:
                return jsonify({'error': 'User account inactive or not found.'}), 401
            g.current_user = user
        finally:
            db.close()
            
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    Decorator to enforce Principal/Administrator privileges.
    Guarantees that teachers and chairman cannot access administrative endpoints.
    Returns HTTP 403 Forbidden with descriptive error if non-admin attempts access.
    """
    @wraps(f)
    @auth_required
    def decorated(*args, **kwargs):
        current_user = getattr(g, 'current_user', None)
        if not current_user or current_user.role not in ['admin', 'principal']:
            return jsonify({
                'error': 'Access forbidden. Principal or Administrator privileges are required to perform this action.',
                'role': current_user.role if current_user else 'anonymous'
            }), 403
        return f(*args, **kwargs)
    return decorated


def chairman_required(f):
    """
    Decorator to enforce Chairman privileges.
    Only the Chairman can access Chairman endpoints.
    """
    @wraps(f)
    @auth_required
    def decorated(*args, **kwargs):
        current_user = getattr(g, 'current_user', None)
        if not current_user or current_user.role != 'chairman':
            return jsonify({
                'error': 'Access forbidden. Chairman privileges are required to perform this action.',
                'role': current_user.role if current_user else 'anonymous'
            }), 403
        return f(*args, **kwargs)
    return decorated


def principal_required(f):
    """
    Decorator to enforce Principal or Administrator privileges.
    Principals manage Teachers and their subject assignments.
    """
    @wraps(f)
    @auth_required
    def decorated(*args, **kwargs):
        current_user = getattr(g, 'current_user', None)
        if not current_user or current_user.role not in ['principal', 'admin']:
            return jsonify({
                'error': 'Access forbidden. Principal or Administrator credentials required.',
                'role': current_user.role if current_user else 'anonymous'
            }), 403
        return f(*args, **kwargs)
    return decorated


def teacher_required(f):
    """
    Decorator to ensure user is an active teacher, principal, or administrator.
    Chairman is strictly blocked from question paper operations.
    """
    @wraps(f)
    @auth_required
    def decorated(*args, **kwargs):
        current_user = getattr(g, 'current_user', None)
        if not current_user or current_user.role not in ['teacher', 'admin', 'principal']:
            return jsonify({
                'error': 'Access forbidden. Teaching or academic operational credentials required.'
            }), 403
        return f(*args, **kwargs)
    return decorated


def validate_teacher_subject_access(user, requested_subject):
    """
    Validate whether the user is authorized for the requested subject.
    Admins and Principals have administrative access across subjects.
    Teachers are strictly restricted to their assigned subjects.
    Returns (is_authorized: bool, error_dict: dict | None, status_code: int | None)
    """
    if not user:
        return False, {'error': 'Authentication required.'}, 401

    if user.role in ['admin', 'principal']:
        return True, None, None

    if user.role == 'teacher':
        assigned = user.assigned_subjects
        if not assigned:
            return False, {
                'success': False,
                'is_valid': False,
                'error': 'No subject assigned. Please contact your Principal.',
                'assigned_subjects': []
            }, 403

        if not requested_subject:
            return False, {
                'success': False,
                'is_valid': False,
                'error': 'Subject selection is mandatory.'
            }, 400

        assigned_lower = [s.strip().lower() for s in assigned]
        if requested_subject.strip().lower() not in assigned_lower:
            return False, {
                'success': False,
                'is_valid': False,
                'error': f"Access forbidden. You are authorized to generate question papers only for your assigned subject(s): {', '.join(assigned)}.",
                'requested_subject': requested_subject,
                'assigned_subjects': assigned
            }, 403

        return True, None, None

    return False, {
        'success': False,
        'is_valid': False,
        'error': f"Access forbidden. Account role '{user.role}' is not authorized for question paper generation."
    }, 403


def log_audit(db, action: str, entity_type: str = None, entity_id: str = None, details: dict = None, user: User = None):
    """
    Record an administrative audit log entry.
    """
    try:
        user_to_log = user or getattr(g, 'current_user', None)
        user_id = user_to_log.id if user_to_log else None
        user_email = user_to_log.email if user_to_log else 'system'
        
        entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            details=details or {},
            created_at=datetime.now(timezone.utc)
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        print(f"Failed to record audit log: {e}")
