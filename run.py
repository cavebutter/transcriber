#!/usr/bin/env python3
import os
import sys
import logging
import time
import signal
import click
from datetime import datetime
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Load environment variables from .env file
load_dotenv()

from app import create_app, celery
from app.models import User, Job


def check_gpu_availability():
    """Fail fast if GPU not available when required."""
    gpu_required = os.environ.get('GPU_AVAILABLE', 'false').lower() == 'true'

    if not gpu_required:
        print("ℹ️  GPU not required for this service")
        return True

    try:
        import torch

        if not torch.cuda.is_available():
            print("❌ CUDA GPU not available. This application requires GPU support.")
            print("   Please ensure NVIDIA drivers and CUDA are properly installed.")
            return False

        gpu_count = torch.cuda.device_count()

        if gpu_count == 0:
            print("❌ No CUDA GPUs detected.")
            return False

        # Test GPU access
        gpu_name = torch.cuda.get_device_name(0)
        memory_total = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3  # GB

        print(f"✅ Found {gpu_count} GPU(s): {gpu_name}")
        print(f"   GPU Memory: {memory_total:.1f} GB")

        # Test basic GPU operation
        test_tensor = torch.cuda.FloatTensor([1.0])
        print(f"✅ GPU test successful")

        return True

    except ImportError:
        print("❌ PyTorch not available. Cannot check GPU status.")
        return False
    except Exception as e:
        print(f"❌ GPU Check Failed: {e}")
        return False


def validate_external_services():
    """Check that required external services are available."""
    print("🔍 Validating external services...")

    # Check Redis connection
    try:
        import redis
        redis_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

    # Check Ollama connection
    try:
        import requests
        ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        response = requests.get(f"{ollama_host}/api/tags", timeout=10)

        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✅ Ollama connection successful ({len(models)} models loaded)")
        else:
            print(f"❌ Ollama returned status code {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ollama connection failed: {e}")
        print(f"   Make sure Ollama is running at {ollama_host}")
        return False

    # Check HuggingFace token if diarization enabled
    hf_token = os.environ.get('HF_TOKEN')
    if not hf_token:
        print("⚠️  HF_TOKEN not set. Speaker diarization will not work.")
    else:
        print("✅ HuggingFace token configured")

    return True


def setup_logging(app):
    """Set up application logging with rotation."""
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')

        # Set up rotating file handler
        file_handler = RotatingFileHandler(
            'logs/realrecap.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )

        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('RealRecap startup')


def setup_signal_handlers():
    """Set up graceful shutdown handlers."""

    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}. Shutting down gracefully...")
        # Give Celery tasks time to finish
        time.sleep(5)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


# Create the Flask application
app = create_app()

# Set up logging
setup_logging(app)

# Set startup time for health checks
app.config['STARTUP_TIME'] = datetime.utcnow().isoformat()

# Configure Celery periodic tasks
from celery.schedules import crontab

celery.conf.beat_schedule = {
    'cleanup-expired-jobs': {
        'task': 'app.tasks.cleanup_expired_jobs',
        'schedule': crontab(minute=0),  # Every hour
    },
}
celery.conf.timezone = 'UTC'

# Apply Celery configuration from app config
celery.conf.update(
    task_routes=app.config.get('CELERY_TASK_ROUTES', {}),
    worker_concurrency=app.config.get('CELERY_WORKER_CONCURRENCY', 1),
    worker_prefetch_multiplier=app.config.get('CELERY_WORKER_PREFETCH_MULTIPLIER', 1),
    task_acks_late=app.config.get('CELERY_TASK_ACKS_LATE', True),
    worker_max_tasks_per_child=app.config.get('CELERY_WORKER_MAX_TASKS_PER_CHILD', 10),
)

# Make celery available at module level for worker
celery = celery


@app.shell_context_processor
def make_shell_context():
    """Register models for flask shell command."""
    return {
        'db': app.extensions['sqlalchemy'].db,
        'User': User,
        'Job': Job,
        'celery': celery
    }


@app.cli.command("init-db")
def init_db_command():
    """Initialize the database."""
    from app import db
    db.create_all()
    print("✅ Database initialized successfully")


@app.cli.command("create-admin")
def create_admin_command():
    """Create an admin user."""
    from app import db
    from app.models import User

    email = input("Admin email: ")
    password = input("Admin password: ")

    if User.query.filter_by(email=email).first():
        print(f"❌ User {email} already exists!")
        return

    admin = User(email=email)
    admin.set_password(password)

    db.session.add(admin)
    db.session.commit()
    print(f"✅ Admin user {email} created successfully!")


@click.option('--force', is_flag=True, help='Force reimport existing models')
@click.option('--timeout', default=300, help='Timeout per model in seconds')
def import_ollama_models(force, timeout):
    """Import custom Ollama models from local directory."""
    import requests
    import time

    ollama_host = app.config.get('OLLAMA_HOST', 'http://localhost:11434')
    models_dir = "ollama-models"

    if not os.path.exists(models_dir):
        print(f"❌ Models directory {models_dir} not found!")
        return

    # Check if Ollama is available
    try:
        response = requests.get(f"{ollama_host}/api/tags", timeout=10)
        response.raise_for_status()
        print(f"✅ Ollama is available at {ollama_host}")
    except Exception as e:
        print(f"❌ Cannot connect to Ollama at {ollama_host}: {e}")
        return

    success_count = 0
    total_models = 0

    for model_dir in os.listdir(models_dir):
        model_path = os.path.join(models_dir, model_dir)
        if os.path.isdir(model_path):
            modelfile_path = os.path.join(model_path, "Modelfile")
            if os.path.exists(modelfile_path):
                total_models += 1
                print(f"📦 Importing model: {model_dir}")

                # Check if model already exists
                if not force:
                    try:
                        existing_models = requests.get(f"{ollama_host}/api/tags").json().get('models', [])
                        if any(model.get('name', '').startswith(model_dir) for model in existing_models):
                            print(f"   ⏭️  Model {model_dir} already exists (use --force to reimport)")
                            success_count += 1
                            continue
                    except:
                        pass  # Continue with import if we can't check

                # Read Modelfile
                try:
                    with open(modelfile_path, 'r') as f:
                        modelfile_content = f.read()

                    # Create model via Ollama API
                    response = requests.post(
                        f"{ollama_host}/api/create",
                        json={
                            "name": model_dir,
                            "modelfile": modelfile_content
                        },
                        timeout=timeout
                    )

                    if response.status_code == 200:
                        print(f"   ✅ Successfully imported {model_dir}")
                        success_count += 1
                    else:
                        print(f"   ❌ Failed to import {model_dir}: {response.text}")

                except Exception as e:
                    print(f"   ❌ Error importing {model_dir}: {e}")

                # Small delay between imports
                time.sleep(2)

    print(f"📊 Import complete: {success_count}/{total_models} models imported successfully")


@app.cli.command("validate-system")
def validate_system_command():
    """Validate system requirements and external services."""
    print("🔍 System Validation")
    print("=" * 50)

    all_good = True

    # Check GPU
    if not check_gpu_availability():
        all_good = False

    # Check external services
    if not validate_external_services():
        all_good = False

    if all_good:
        print("\n🎉 All system checks passed!")
    else:
        print("\n❌ Some system checks failed. Please review the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()

    # Perform startup validation
    print("🎯 RealRecap Starting Up...")
    print("=" * 50)

    # Only validate GPU and services if we're running the main app
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] not in ['shell', 'init-db', 'create-admin']):
        if not check_gpu_availability():
            print("❌ Startup failed: GPU validation failed")
            sys.exit(1)

        if not validate_external_services():
            print("❌ Startup failed: External service validation failed")
            sys.exit(1)

    print("✅ All startup checks passed!")
    print(f"🚀 Starting RealRecap server on 0.0.0.0:5000")

    # For development - use gunicorn or flask run in production
    app.run(host='0.0.0.0', port=5000, debug=True)