import os
import uuid
from flask import render_template, request, flash, redirect, url_for, send_file, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.main import bp
from app.forms import AudioUploadForm, TranscriptUploadForm
from app.models import Job, JobType, JobStatus
from app.tasks import process_audio_task, process_transcript_task


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/dashboard')
@login_required
def dashboard():
    # Get user's recent jobs
    jobs = current_user.get_active_jobs().limit(20).all()
    return render_template('dashboard.html', jobs=jobs)


@bp.route('/upload/audio', methods=['GET', 'POST'])
@login_required
def upload_audio():
    form = AudioUploadForm()

    if form.validate_on_submit():
        try:
            # Create job record
            job = Job(
                user_id=current_user.id,
                job_type=JobType.AUDIO_PROCESSING,
                title=form.title.data or form.audio_file.data.filename,
                original_filename=form.audio_file.data.filename,
                whisper_model=form.whisper_model.data,
                summarizer_model=form.summarizer_model.data,
                enable_diarization=form.enable_diarization.data,
                min_speakers=form.min_speakers.data,
                max_speakers=form.max_speakers.data,
                output_format=form.output_format.data
            )

            db.session.add(job)
            db.session.flush()  # Get the job ID

            # Create user-specific directory
            user_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(current_user.id))
            job_dir = os.path.join(user_dir, str(job.id))
            os.makedirs(job_dir, exist_ok=True)

            # Save uploaded file
            filename = secure_filename(form.audio_file.data.filename)
            # Add timestamp to avoid conflicts
            name, ext = os.path.splitext(filename)
            unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"

            file_path = os.path.join(job_dir, unique_filename)
            form.audio_file.data.save(file_path)

            # Update job with file paths
            job.input_file_path = os.path.relpath(file_path, current_app.config['UPLOAD_FOLDER'])
            job.output_dir_path = os.path.relpath(job_dir, current_app.config['UPLOAD_FOLDER'])

            db.session.commit()

            # Start background task
            task = process_audio_task.delay(job.id)
            job.celery_task_id = task.id
            db.session.commit()

            flash(f'Audio file uploaded successfully! Job #{job.id} is being processed.', 'success')
            return redirect(url_for('main.job_status', job_id=job.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error uploading audio: {e}")
            flash('An error occurred while uploading your file. Please try again.', 'error')

    return render_template('upload_audio.html', form=form)


@bp.route('/upload/transcript', methods=['GET', 'POST'])
@login_required
def upload_transcript():
    form = TranscriptUploadForm()

    if form.validate_on_submit():
        try:
            # Create job record
            job = Job(
                user_id=current_user.id,
                job_type=JobType.TRANSCRIPT_SUMMARY,
                title=form.title.data or form.transcript_file.data.filename,
                original_filename=form.transcript_file.data.filename,
                summarizer_model=form.summarizer_model.data,
                output_format=form.output_format.data
            )

            db.session.add(job)
            db.session.flush()  # Get the job ID

            # Create user-specific directory
            user_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(current_user.id))
            job_dir = os.path.join(user_dir, str(job.id))
            os.makedirs(job_dir, exist_ok=True)

            # Save uploaded file
            filename = secure_filename(form.transcript_file.data.filename)
            # Add timestamp to avoid conflicts
            name, ext = os.path.splitext(filename)
            unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"

            file_path = os.path.join(job_dir, unique_filename)
            form.transcript_file.data.save(file_path)

            # Update job with file paths
            job.input_file_path = os.path.relpath(file_path, current_app.config['UPLOAD_FOLDER'])
            job.output_dir_path = os.path.relpath(job_dir, current_app.config['UPLOAD_FOLDER'])

            db.session.commit()

            # Start background task
            task = process_transcript_task.delay(job.id)
            job.celery_task_id = task.id
            db.session.commit()

            flash(f'Transcript uploaded successfully! Job #{job.id} is being processed.', 'success')
            return redirect(url_for('main.job_status', job_id=job.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error uploading transcript: {e}")
            flash('An error occurred while uploading your file. Please try again.', 'error')

    return render_template('upload_transcript.html', form=form)


@bp.route('/job/<int:job_id>')
@login_required
def job_status(job_id):
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    return render_template('job_status.html', job=job)


@bp.route('/download/<int:job_id>/<path:filename>')
@login_required
def download_file(job_id, filename):
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()

    if not job.can_download:
        flash('This file is no longer available for download.', 'error')
        return redirect(url_for('main.dashboard'))

    # Security check: ensure filename is in the job's output directory
    output_files = job.get_output_files()
    file_info = next((f for f in output_files if f['filename'] == filename), None)

    if not file_info:
        flash('File not found.', 'error')
        return redirect(url_for('main.job_status', job_id=job_id))

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_info['path'])

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename
    )


@bp.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()

    try:
        # Cancel celery task if still running
        if job.celery_task_id and job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
            from celery import current_app as celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)

        # Clean up files
        job.cleanup_files()

        # Delete job record
        db.session.delete(job)
        db.session.commit()

        flash(f'Job #{job_id} has been deleted.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting job {job_id}: {e}")
        flash('An error occurred while deleting the job.', 'error')

    return redirect(url_for('main.dashboard'))