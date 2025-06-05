from flask import jsonify, request, current_app
from flask_login import login_required, current_user
from celery.result import AsyncResult

from app.api import bp
from app.models import Job, JobStatus
from app import celery


@bp.route('/job/<int:job_id>/status')
@login_required
def job_status(job_id):
    """Get current status of a job via AJAX."""
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first()

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # Get Celery task status if available
    task_info = None
    if job.celery_task_id:
        try:
            task = AsyncResult(job.celery_task_id, app=celery)
            task_info = {
                'task_id': job.celery_task_id,
                'state': task.state,
                'info': task.info if task.info else {}
            }
        except Exception as e:
            current_app.logger.warning(f"Could not get task info for {job.celery_task_id}: {e}")

    # Get output files if completed
    output_files = []
    if job.can_download:
        output_files = job.get_output_files()

    return jsonify({
        'job_id': job.id,
        'status': job.status.value,
        'progress_percent': job.progress_percent,
        'progress_message': job.progress_message,
        'error_message': job.error_message,
        'created_at': job.created_at.isoformat(),
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'expires_at': job.expires_at.isoformat(),
        'is_expired': job.is_expired,
        'can_download': job.can_download,
        'output_files': output_files,
        'task_info': task_info
    })


@bp.route('/jobs')
@login_required
def list_jobs():
    """Get list of user's jobs."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)  # Max 50 per page

    jobs_query = current_user.get_active_jobs()
    jobs_paginated = jobs_query.paginate(
        page=page, per_page=per_page, error_out=False
    )

    jobs_data = []
    for job in jobs_paginated.items:
        jobs_data.append({
            'job_id': job.id,
            'title': job.title,
            'job_type': job.job_type.value,
            'status': job.status.value,
            'progress_percent': job.progress_percent,
            'created_at': job.created_at.isoformat(),
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'can_download': job.can_download,
            'output_files_count': len(job.get_output_files()) if job.can_download else 0
        })

    return jsonify({
        'jobs': jobs_data,
        'pagination': {
            'page': jobs_paginated.page,
            'pages': jobs_paginated.pages,
            'per_page': jobs_paginated.per_page,
            'total': jobs_paginated.total,
            'has_next': jobs_paginated.has_next,
            'has_prev': jobs_paginated.has_prev
        }
    })


@bp.route('/job/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel a running job."""
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first()

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
        return jsonify({'error': 'Job cannot be cancelled'}), 400

    try:
        # Cancel Celery task
        if job.celery_task_id:
            celery.control.revoke(job.celery_task_id, terminate=True)

        # Update job status
        job.status = JobStatus.FAILED
        job.error_message = "Cancelled by user"
        job.progress_message = "Cancelled"
        job.progress_percent = 0

        from app import db
        db.session.commit()

        return jsonify({
            'message': 'Job cancelled successfully',
            'job_id': job.id,
            'status': job.status.value
        })

    except Exception as e:
        current_app.logger.error(f"Error cancelling job {job_id}: {e}")
        return jsonify({'error': 'Failed to cancel job'}), 500


@bp.route('/system/health')
def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        from app import db
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))

        # Check Celery connection
        inspect = celery.control.inspect()
        active_tasks = inspect.active()

        # Check Ollama connection
        import requests
        ollama_host = current_app.config.get('OLLAMA_HOST', 'http://localhost:11434')
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=5)
            ollama_status = "ok" if response.status_code == 200 else "error"
        except:
            ollama_status = "unreachable"

        return jsonify({
            'status': 'healthy',
            'database': 'ok',
            'celery': 'ok' if active_tasks is not None else 'error',
            'ollama': ollama_status,
            'timestamp': current_app.config.get('STARTUP_TIME', 'unknown')
        })

    except Exception as e:
        current_app.logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@bp.route('/system/stats')
@login_required
def system_stats():
    """Get system statistics (admin only for now)."""
    try:
        from app.models import User, Job
        from sqlalchemy import func

        # Basic stats
        total_users = User.query.count()
        total_jobs = Job.query.count()
        active_jobs = Job.query.filter(Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])).count()

        # Job stats by status
        job_stats = db.session.query(
            Job.status, func.count(Job.id)
        ).group_by(Job.status).all()

        # Recent activity (last 24 hours)
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_jobs = Job.query.filter(Job.created_at > recent_cutoff).count()

        return jsonify({
            'total_users': total_users,
            'total_jobs': total_jobs,
            'active_jobs': active_jobs,
            'recent_jobs_24h': recent_jobs,
            'job_stats': {status.value: count for status, count in job_stats}
        })

    except Exception as e:
        current_app.logger.error(f"Error getting system stats: {e}")
        return jsonify({'error': 'Failed to get system stats'}), 500