from datetime import datetime, timedelta
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import enum
import os
import shutil

from app import db


class JobType(enum.Enum):
    AUDIO_PROCESSING = "audio_processing"
    TRANSCRIPT_SUMMARY = "transcript_summary"


class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    jobs = db.relationship('Job', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_active_jobs(self):
        """Get all non-expired jobs for this user."""
        expiry_time = datetime.utcnow() - timedelta(hours=current_app.config['JOB_EXPIRY_HOURS'])
        return self.jobs.filter(Job.created_at > expiry_time).order_by(Job.created_at.desc())

    def __repr__(self):
        return f'<User {self.email}>'


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Job metadata
    job_type = db.Column(db.Enum(JobType), nullable=False)
    status = db.Column(db.Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    # Job parameters
    title = db.Column(db.String(200))
    original_filename = db.Column(db.String(200))
    whisper_model = db.Column(db.String(50))
    summarizer_model = db.Column(db.String(50))
    enable_diarization = db.Column(db.Boolean, default=False)
    min_speakers = db.Column(db.Integer)
    max_speakers = db.Column(db.Integer)
    output_format = db.Column(db.String(10), default='pdf')

    # File paths (relative to upload folder)
    input_file_path = db.Column(db.String(500))
    output_dir_path = db.Column(db.String(500))

    # Processing results
    error_message = db.Column(db.Text)
    progress_message = db.Column(db.String(200))
    progress_percent = db.Column(db.Integer, default=0)

    # Celery task ID for tracking
    celery_task_id = db.Column(db.String(50))

    def __init__(self, **kwargs):
        super(Job, self).__init__(**kwargs)
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(hours=current_app.config['JOB_EXPIRY_HOURS'])

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @property
    def can_download(self):
        return self.status == JobStatus.COMPLETED and not self.is_expired

    def get_output_files(self):
        """Get list of output files that exist."""
        if not self.output_dir_path or not self.can_download:
            return []

        output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], self.output_dir_path)
        if not os.path.exists(output_dir):
            return []

        files = []
        for filename in os.listdir(output_dir):
            if filename.endswith(('.pdf', '.md', '.html', '.txt', '.json')):
                file_path = os.path.join(output_dir, filename)
                file_size = os.path.getsize(file_path)
                files.append({
                    'filename': filename,
                    'path': os.path.join(self.output_dir_path, filename),
                    'size': file_size,
                    'size_human': self._human_readable_size(file_size)
                })
        return files

    def cleanup_files(self):
        """Remove all files associated with this job."""
        if self.input_file_path:
            input_path = os.path.join(current_app.config['UPLOAD_FOLDER'], self.input_file_path)
            if os.path.exists(input_path):
                os.remove(input_path)

        if self.output_dir_path:
            output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], self.output_dir_path)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)

    def set_error(self, error_message):
        """Mark job as failed with error message."""
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        db.session.commit()

    def update_progress(self, message, percent=None):
        """Update job progress."""
        self.progress_message = message
        if percent is not None:
            self.progress_percent = max(0, min(100, percent))
        db.session.commit()

    def mark_completed(self):
        """Mark job as completed."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress_percent = 100
        self.progress_message = "Completed successfully"
        db.session.commit()

    @staticmethod
    def _human_readable_size(size):
        """Convert bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    @staticmethod
    def cleanup_expired_jobs():
        """Clean up expired jobs and their files."""
        expired_jobs = Job.query.filter(Job.expires_at < datetime.utcnow()).all()

        for job in expired_jobs:
            try:
                job.cleanup_files()
                db.session.delete(job)
            except Exception as e:
                current_app.logger.error(f"Error cleaning up job {job.id}: {e}")

        db.session.commit()
        return len(expired_jobs)

    def __repr__(self):
        return f'<Job {self.id}: {self.job_type.value} - {self.status.value}>'