#!/usr/bin/env python3
"""
RealRecap CLI Helper

A command-line interface for common development and administration tasks.
"""

import click
import os
import sys
import subprocess
import requests
from datetime import datetime, timedelta
from pathlib import Path


@click.group()
def cli():
    """RealRecap CLI - Development and administration helper."""
    pass


@cli.command()
def setup():
    """Run the full setup process."""
    click.echo("🎯 Running RealRecap setup...")
    subprocess.run([sys.executable, "setup.py"])


@cli.command()
@click.option('--host', default='localhost', help='Host to run on')
@click.option('--port', default=5000, help='Port to run on')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def runserver(host, port, debug):
    """Start the development server."""
    os.environ['FLASK_ENV'] = 'development' if debug else 'production'

    click.echo(f"🚀 Starting RealRecap on {host}:{port}")
    subprocess.run([sys.executable, "run.py"])


@cli.command()
@click.option('--concurrency', default=2, help='Number of worker processes')
@click.option('--loglevel', default='info', help='Log level')
def celery(concurrency, loglevel):
    """Start Celery worker."""
    click.echo(f"🔄 Starting Celery worker with {concurrency} processes")
    subprocess.run([
        'celery', '-A', 'run.celery', 'worker',
        '--concurrency', str(concurrency),
        '--loglevel', loglevel
    ])


@cli.command()
def beat():
    """Start Celery beat scheduler."""
    click.echo("⏰ Starting Celery beat scheduler")
    subprocess.run(['celery', '-A', 'run.celery', 'beat', '--loglevel=info'])


@cli.command()
def monitor():
    """Start Celery monitoring tool."""
    click.echo("📊 Starting Celery monitor")
    subprocess.run(['celery', '-A', 'run.celery', 'flower'])


@cli.command()
def initdb():
    """Initialize the database."""
    try:
        from app import create_app, db

        app = create_app()
        with app.app_context():
            db.create_all()
            click.echo("✅ Database initialized successfully")
    except Exception as e:
        click.echo(f"❌ Failed to initialize database: {e}")
        sys.exit(1)


@cli.command()
@click.option('--email', prompt=True, help='Admin email address')
@click.option('--password', prompt=True, hide_input=True, help='Admin password')
def createadmin(email, password):
    """Create an admin user."""
    try:
        from app import create_app, db
        from app.models import User

        app = create_app()
        with app.app_context():
            # Check if user exists
            if User.query.filter_by(email=email).first():
                click.echo(f"❌ User {email} already exists")
                return

            # Create user
            admin = User(email=email)
            admin.set_password(password)

            db.session.add(admin)
            db.session.commit()

            click.echo(f"✅ Admin user {email} created successfully")
    except Exception as e:
        click.echo(f"❌ Failed to create admin user: {e}")
        sys.exit(1)


@cli.command()
def cleanup():
    """Clean up expired jobs and files."""
    try:
        from app import create_app
        from app.models import Job

        app = create_app()
        with app.app_context():
            count = Job.cleanup_expired_jobs()
            click.echo(f"✅ Cleaned up {count} expired jobs")
    except Exception as e:
        click.echo(f"❌ Failed to clean up jobs: {e}")
        sys.exit(1)


@cli.command()
def status():
    """Check system status."""
    click.echo("🔍 Checking RealRecap system status...")

    # Check Flask app
    try:
        response = requests.get('http://localhost:5000/api/system/health', timeout=5)
        if response.status_code == 200:
            data = response.json()
            click.echo("✅ Flask app: Running")
            click.echo(f"   Database: {data.get('database', 'Unknown')}")
            click.echo(f"   Celery: {data.get('celery', 'Unknown')}")
            click.echo(f"   Ollama: {data.get('ollama', 'Unknown')}")
        else:
            click.echo("❌ Flask app: Not responding")
    except requests.exceptions.RequestException:
        click.echo("❌ Flask app: Not running")

    # Check Redis
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        click.echo("✅ Redis: Running")
    except Exception:
        click.echo("❌ Redis: Not running")

    # Check Ollama
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            click.echo(f"✅ Ollama: Running ({len(models)} models loaded)")
        else:
            click.echo("❌ Ollama: Not responding")
    except requests.exceptions.RequestException:
        click.echo("❌ Ollama: Not running")


@cli.command()
def models():
    """List and manage Ollama models."""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            click.echo(f"📋 Available Ollama models ({len(models)}):")
            for model in models:
                name = model.get('name', 'Unknown')
                size = model.get('size', 0)
                size_gb = size / (1024 ** 3) if size else 0
                click.echo(f"   • {name} ({size_gb:.1f}GB)")
        else:
            click.echo("❌ Failed to fetch models from Ollama")
    except requests.exceptions.RequestException:
        click.echo("❌ Cannot connect to Ollama")


@cli.command()
def importmodels():
    """Import custom Ollama models."""
    models_dir = Path('ollama-models')
    if not models_dir.exists():
        click.echo("❌ ollama-models directory not found")
        return

    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    success_count = 0

    for model_dir in models_dir.iterdir():
        if model_dir.is_dir():
            modelfile_path = model_dir / 'Modelfile'
            if modelfile_path.exists():
                click.echo(f"📦 Importing model: {model_dir.name}")

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
                        click.echo(f"   ✅ Successfully imported {model_dir.name}")
                        success_count += 1
                    else:
                        click.echo(f"   ❌ Failed to import {model_dir.name}")

                except Exception as e:
                    click.echo(f"   ❌ Error importing {model_dir.name}: {e}")

    click.echo(f"📊 Import complete: {success_count} models imported")


@cli.command()
@click.option('--days', default=1, help='Number of days to show')
def stats(days):
    """Show usage statistics."""
    try:
        from app import create_app, db
        from app.models import User, Job, JobStatus
        from sqlalchemy import func

        app = create_app()
        with app.app_context():
            # Basic stats
            total_users = User.query.count()
            total_jobs = Job.query.count()
            active_jobs = Job.query.filter(
                Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
            ).count()

            # Recent activity
            cutoff = datetime.utcnow() - timedelta(days=days)
            recent_jobs = Job.query.filter(Job.created_at > cutoff).count()

            # Job stats by status
            job_stats = db.session.query(
                Job.status, func.count(Job.id)
            ).group_by(Job.status).all()

            click.echo(f"📊 RealRecap Statistics (Last {days} days)")
            click.echo(f"   👥 Total users: {total_users}")
            click.echo(f"   📋 Total jobs: {total_jobs}")
            click.echo(f"   🔄 Active jobs: {active_jobs}")
            click.echo(f"   📈 Recent jobs: {recent_jobs}")
            click.echo("   📊 Job status breakdown:")
            for status, count in job_stats:
                click.echo(f"      • {status.value}: {count}")

    except Exception as e:
        click.echo(f"❌ Failed to get statistics: {e}")


@cli.command()
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.option('--lines', '-n', default=50, help='Number of lines to show')
def logs(follow, lines):
    """Show application logs."""
    log_file = Path('logs/realrecap.log')

    if not log_file.exists():
        click.echo("❌ Log file not found")
        return

    if follow:
        subprocess.run(['tail', '-f', str(log_file)])
    else:
        subprocess.run(['tail', '-n', str(lines), str(log_file)])


@cli.command()
def test():
    """Run the test suite."""
    click.echo("🧪 Running tests...")
    result = subprocess.run(['pytest', 'tests/', '-v'])
    sys.exit(result.returncode)


@cli.command()
def shell():
    """Start an interactive shell with app context."""
    try:
        from app import create_app, db
        from app.models import User, Job

        app = create_app()

        with app.app_context():
            # Make commonly used objects available
            ctx = {
                'app': app,
                'db': db,
                'User': User,
                'Job': Job
            }

            # Start IPython shell if available, otherwise use basic Python shell
            try:
                from IPython import start_ipython
                start_ipython(argv=[], user_ns=ctx)
            except ImportError:
                import code
                code.interact(local=ctx)

    except Exception as e:
        click.echo(f"❌ Failed to start shell: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()