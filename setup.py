#!/usr/bin/env python3
"""
RealRecap Setup Script

This script helps set up the RealRecap application for development or production.
It handles database initialization, model setup, and basic configuration.
"""

import os
import sys
import subprocess
import requests
import time
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")


def check_system_dependencies():
    """Check for required system dependencies."""
    dependencies = {
        'ffmpeg': 'Audio processing',
        'pandoc': 'PDF generation',
        'xelatex': 'LaTeX PDF engine'
    }

    missing = []
    for cmd, purpose in dependencies.items():
        if subprocess.run(['which', cmd], capture_output=True).returncode != 0:
            missing.append(f"{cmd} ({purpose})")

    if missing:
        print("❌ Missing system dependencies:")
        for dep in missing:
            print(f"   - {dep}")
        print("\nInstall commands:")
        print("Ubuntu/Debian: sudo apt install ffmpeg pandoc texlive-xetex")
        print("macOS: brew install ffmpeg pandoc mactex")
        sys.exit(1)

    print("✅ All system dependencies found")


def setup_environment():
    """Set up environment file if it doesn't exist."""
    env_path = Path('.env')
    env_example_path = Path('.env.example')

    if not env_path.exists():
        if env_example_path.exists():
            # Copy example to .env
            with open(env_example_path) as f:
                content = f.read()

            with open(env_path, 'w') as f:
                f.write(content)

            print("✅ Created .env file from template")
            print("🔧 Please edit .env file with your configuration")
        else:
            print("❌ No .env.example file found")
            return False
    else:
        print("✅ .env file already exists")

    return True


def install_python_dependencies():
    """Install Python dependencies."""
    print("📦 Installing Python dependencies...")

    requirements_files = ['requirements-webapp.txt', 'requirements-new.txt', 'requirements.txt']
    requirements_file = None

    for req_file in requirements_files:
        if Path(req_file).exists():
            requirements_file = req_file
            break

    if not requirements_file:
        print("❌ No requirements file found")
        return False

    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', requirements_file
        ], check=True)
        print(f"✅ Installed dependencies from {requirements_file}")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Failed to install dependencies from {requirements_file}")
        return False


def check_ollama():
    """Check if Ollama is running and accessible."""
    print("🔍 Checking Ollama connection...")

    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

    try:
        response = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama is running and accessible")
            return True
        else:
            print(f"❌ Ollama returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print(f"   Make sure Ollama is running at {ollama_host}")
        return False


def setup_ollama_models():
    """Set up custom Ollama models."""
    print("🤖 Setting up Ollama models...")

    models_dir = Path('ollama-models')
    if not models_dir.exists():
        print("❌ ollama-models directory not found")
        return False

    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    success_count = 0

    for model_dir in models_dir.iterdir():
        if model_dir.is_dir():
            modelfile_path = model_dir / 'Modelfile'
            if modelfile_path.exists():
                print(f"   Installing model: {model_dir.name}")

                try:
                    with open(modelfile_path, 'r') as f:
                        modelfile_content = f.read()

                    response = requests.post(
                        f"{ollama_host}/api/create",
                        json={
                            "name": model_dir.name,
                            "modelfile": modelfile_content
                        },
                        timeout=300
                    )

                    if response.status_code == 200:
                        print(f"   ✅ Successfully installed {model_dir.name}")
                        success_count += 1
                    else:
                        print(f"   ❌ Failed to install {model_dir.name}: {response.text}")

                except Exception as e:
                    print(f"   ❌ Error installing {model_dir.name}: {e}")

                time.sleep(2)  # Small delay between installs

    if success_count > 0:
        print(f"✅ Successfully installed {success_count} Ollama models")
        return True
    else:
        print("❌ No models were successfully installed")
        return False


def initialize_database():
    """Initialize the database."""
    print("🗄️  Initializing database...")

    try:
        # Import here to avoid issues if dependencies aren't installed yet
        from app import create_app, db

        app = create_app()
        with app.app_context():
            db.create_all()
            print("✅ Database initialized successfully")
            return True
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False


def create_admin_user():
    """Optionally create an admin user."""
    response = input("🔐 Would you like to create an admin user? (y/n): ")
    if response.lower() != 'y':
        return True

    try:
        from app import create_app, db
        from app.models import User

        email = input("Admin email: ")
        password = input("Admin password: ")

        app = create_app()
        with app.app_context():
            # Check if user already exists
            if User.query.filter_by(email=email).first():
                print(f"❌ User {email} already exists")
                return False

            # Create user
            admin = User(email=email)
            admin.set_password(password)

            db.session.add(admin)
            db.session.commit()

            print(f"✅ Admin user {email} created successfully")
            return True
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")
        return False


def check_redis():
    """Check if Redis is running (for Celery)."""
    print("🔍 Checking Redis connection...")

    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis is running and accessible")
        return True
    except Exception as e:
        print(f"❌ Cannot connect to Redis: {e}")
        print("   Make sure Redis is running on localhost:6379")
        return False


def main():
    """Main setup function."""
    print("🎯 RealRecap Setup Script")
    print("=" * 50)

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Step 1: Check Python version
    check_python_version()

    # Step 2: Check system dependencies
    check_system_dependencies()

    # Step 3: Set up environment
    if not setup_environment():
        return

    # Reload environment after setup
    load_dotenv()

    # Step 4: Install Python dependencies
    if not install_python_dependencies():
        print("❌ Setup failed at dependency installation")
        return

    # Step 5: Check external services
    ollama_ok = check_ollama()
    redis_ok = check_redis()

    if not (ollama_ok and redis_ok):
        print("⚠️  Some external services are not available")
        print("   The application may not work properly until they are running")

    # Step 6: Set up Ollama models (if Ollama is available)
    if ollama_ok:
        setup_ollama_models()

    # Step 7: Initialize database
    if not initialize_database():
        print("❌ Setup failed at database initialization")
        return

    # Step 8: Create admin user
    create_admin_user()

    print("\n" + "=" * 50)
    print("🎉 Setup completed!")
    print("\nNext steps:")
    print("1. Edit .env file with your configuration")
    print("2. Start Redis: redis-server")
    print("3. Start Ollama: ollama serve")
    print("4. Start the application:")
    print("   - Development: python run.py")
    print("   - Production: docker-compose up")
    print("5. Start Celery worker in another terminal:")
    print("   celery -A run.celery worker --loglevel=info")


if __name__ == "__main__":
    main()