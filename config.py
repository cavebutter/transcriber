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

    # GPU Task Routing - All GPU tasks go to gpu_queue with concurrency=1
    CELERY_TASK_ROUTES = {
        'app.tasks.process_audio_task': {'queue': 'gpu_queue'},
        'app.tasks.process_transcript_task': {'queue': 'gpu_queue'},  # Uses Ollama via GPU worker
    }

    # Celery Worker Configuration
    CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', 1))  # Single GPU worker
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Process one task at a time
    CELERY_TASK_ACKS_LATE = True  # Don't ack until task completes
    CELERY_WORKER_MAX_TASKS_PER_CHILD = 10  # Restart worker after 10 tasks to prevent memory leaks

    # Job settings
    JOB_EXPIRY_HOURS = int(os.environ.get('JOB_EXPIRY_HOURS', 24))
    CLEANUP_INTERVAL_MINUTES = int(os.environ.get('CLEANUP_INTERVAL_MINUTES', 60))
    MAX_CONCURRENT_JOBS = int(os.environ.get('MAX_CONCURRENT_JOBS', 1))  # Limit concurrent GPU jobs

    # Ollama settings
    OLLAMA_HOST = os.environ.get('OLLAMA_HOST') or 'http://localhost:11434'
    DEFAULT_WHISPER_MODEL = os.environ.get('DEFAULT_WHISPER_MODEL', 'large')
    DEFAULT_SUMMARIZER_MODEL = os.environ.get('DEFAULT_SUMMARIZER_MODEL', 'qwen3-summarizer:14b')

    # HuggingFace
    HF_TOKEN = os.environ.get('HF_TOKEN')

    # GPU Configuration
    GPU_AVAILABLE = os.environ.get('GPU_AVAILABLE', 'false').lower() == 'true'
    CUDA_VISIBLE_DEVICES = os.environ.get('CUDA_VISIBLE_DEVICES', '0')
    ENABLE_GPU_FALLBACK = os.environ.get('ENABLE_GPU_FALLBACK', 'false').lower() == 'true'

    # Processing Limits
    MAX_AUDIO_LENGTH_MINUTES = int(os.environ.get('MAX_AUDIO_LENGTH_MINUTES', 180))  # 3 hours max
    MAX_FILE_AGE_HOURS = int(os.environ.get('MAX_FILE_AGE_HOURS', 24))

    # Task Timeouts (in seconds)
    TRANSCRIPTION_TIMEOUT = int(os.environ.get('TRANSCRIPTION_TIMEOUT', 3600))  # 1 hour
    DIARIZATION_TIMEOUT = int(os.environ.get('DIARIZATION_TIMEOUT', 1800))  # 30 minutes
    SUMMARIZATION_TIMEOUT = int(os.environ.get('SUMMARIZATION_TIMEOUT', 600))  # 10 minutes

    # Security
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///realrecap_dev.db'

    # More verbose logging in development
    CELERY_WORKER_LOGLEVEL = 'debug'

    # Shorter timeouts for development
    TRANSCRIPTION_TIMEOUT = 1800  # 30 minutes
    DIARIZATION_TIMEOUT = 900  # 15 minutes
    SUMMARIZATION_TIMEOUT = 300  # 5 minutes


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'postgresql://user:password@localhost/realrecap'

    # Production optimizations
    CELERY_WORKER_LOGLEVEL = 'info'

    # Stricter limits in production
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB in production
    JOB_EXPIRY_HOURS = 12  # Shorter expiry in production


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

    # Disable GPU for testing
    GPU_AVAILABLE = False

    # Fast timeouts for testing
    TRANSCRIPTION_TIMEOUT = 60
    DIARIZATION_TIMEOUT = 60
    SUMMARIZATION_TIMEOUT = 60


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}