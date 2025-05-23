#!/usr/bin/env python3
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app import create_app, celery
from app.models import User, Job

# Create the Flask application
app = create_app()

# Configure logging
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')

    file_handler = logging.FileHandler('logs/realrecap.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info('RealRecap startup')

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
    print("Initialized the database.")


@app.cli.command("create-admin")
def create_admin_command():
    """Create an admin user."""
    from app import db
    from app.models import User

    email = input("Admin email: ")
    password = input("Admin password: ")

    if User.query.filter_by(email=email).first():
        print(f"User {email} already exists!")
        return

    admin = User(email=email)
    admin.set_password(password)

    db.session.add(admin)
    db.session.commit()
    print(f"Admin user {email} created successfully!")


@app.cli.command("import-ollama-models")
def import_ollama_models():
    """Import custom Ollama models from local directory."""
    import requests
    import time

    ollama_host = app.config.get('OLLAMA_HOST', 'http://localhost:11434')
    models_dir = "ollama-models"

    if not os.path.exists(models_dir):
        print(f"Models directory {models_dir} not found!")
        return

    for model_dir in os.listdir(models_dir):
        model_path = os.path.join(models_dir, model_dir)
        if os.path.isdir(model_path):
            modelfile_path = os.path.join(model_path, "Modelfile")
            if os.path.exists(modelfile_path):
                print(f"Importing model: {model_dir}")

                # Read Modelfile
                with open(modelfile_path, 'r') as f:
                    modelfile_content = f.read()

                # Create model via Ollama API
                try:
                    response = requests.post(
                        f"{ollama_host}/api/create",
                        json={
                            "name": model_dir,
                            "modelfile": modelfile_content
                        },
                        timeout=300  # 5 minutes
                    )

                    if response.status_code == 200:
                        print(f"Successfully imported {model_dir}")
                    else:
                        print(f"Failed to import {model_dir}: {response.text}")

                except requests.exceptions.RequestException as e:
                    print(f"Error importing {model_dir}: {e}")

                # Small delay between imports
                time.sleep(2)

    print("Model import complete!")


if __name__ == '__main__':
    # For development - use flask run in production
    app.run(host='0.0.0.0', port=5000, debug=True)