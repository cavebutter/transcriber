import os
from datetime import timedelta


class Config:
    # Basic Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///realrecap.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_AUDIO_EXTENSIONS = {'wav', 'mp3', 'm4a', 'mp4', 'flac', 'ogg'}
    ALLOWED_TRANSCRIPT_EXTENSIONS = {'txt', 'docx'}

    # Celery/Redis
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'

    # Job settings
    JOB_EXPIRY_HOURS = 24
    CLEANUP_INTERVAL_MINUTES = 60

    # Ollama settings
    OLLAMA_HOST = os.environ.get('OLLAMA_HOST') or 'http://localhost:11434'
    DEFAULT_WHISPER_MODEL = 'large'
    DEFAULT_SUMMARIZER_MODEL = 'qwen3-summarizer:14b'

    # HuggingFace
    HF_TOKEN = os.environ.get('HF_TOKEN')

    # Security
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///realrecap_dev.db'


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'postgresql://user:password@localhost/realrecap'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}