import os
import tempfile
import shutil
from celery import current_task
from flask import current_app

from app import celery, db
from app.models import Job, JobStatus
from app.utils.transcription import TranscriptionProcessor
from app.utils.summarization import SummarizationProcessor


def update_job_progress(job_id, message, percent=None):
    """Update job progress in database and send to client via Celery."""
    try:
        job = Job.query.get(job_id)
        if job:
            job.update_progress(message, percent)

            # Send progress update to Celery for real-time updates
            if current_task:
                current_task.update_state(
                    state='PROGRESS',
                    meta={'current': percent or 0, 'total': 100, 'status': message}
                )
    except Exception as e:
        current_app.logger.error(f"Error updating job progress: {e}")


@celery.task(bind=True)
def process_audio_task(self, job_id):
    """Process uploaded audio file through transcription, diarization, and summarization."""
    job = None
    temp_dir = None

    try:
        # Get job from database
        job = Job.query.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.PROCESSING
        db.session.commit()

        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"realrecap_job_{job_id}_")

        # Initialize processors
        transcription_processor = TranscriptionProcessor(
            whisper_model=job.whisper_model,
            enable_diarization=job.enable_diarization,
            min_speakers=job.min_speakers,
            max_speakers=job.max_speakers,
            temp_dir=temp_dir
        )

        summarization_processor = SummarizationProcessor(
            model_name=job.summarizer_model,
            ollama_host=current_app.config['OLLAMA_HOST']
        )

        # Get file paths
        input_file = os.path.join(current_app.config['UPLOAD_FOLDER'], job.input_file_path)
        output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], job.output_dir_path)

        # Step 1: Audio conversion and transcription
        update_job_progress(job_id, "Converting audio format...", 10)
        wav_file = transcription_processor.convert_to_wav(input_file, temp_dir)

        update_job_progress(job_id, f"Transcribing with {job.whisper_model} model...", 20)
        transcription_result = transcription_processor.transcribe_audio(wav_file)

        # Step 2: Speaker diarization (if enabled)
        diarization_result = None
        if job.enable_diarization:
            update_job_progress(job_id, "Performing speaker diarization...", 50)
            diarization_result = transcription_processor.perform_diarization(wav_file)

        # Step 3: Combine transcription and diarization
        update_job_progress(job_id, "Creating transcript...", 60)
        if diarization_result:
            transcript_file = transcription_processor.create_diarized_transcript(
                transcription_result, diarization_result, temp_dir
            )
        else:
            transcript_file = transcription_processor.create_simple_transcript(
                transcription_result, temp_dir
            )

        # Step 4: Summarization
        update_job_progress(job_id, f"Generating summary with {job.summarizer_model}...", 70)
        summary_result = summarization_processor.process_transcript(
            transcript_file,
            title=job.title,
            output_format=job.output_format
        )

        # Step 5: Save results to output directory
        update_job_progress(job_id, "Saving results...", 90)

        # Copy transcription files
        base_name = os.path.splitext(os.path.basename(input_file))[0]

        if diarization_result:
            shutil.copy2(transcript_file, os.path.join(output_dir, f"{base_name}_diarized_transcript.txt"))
        else:
            shutil.copy2(transcript_file, os.path.join(output_dir, f"{base_name}_transcript.txt"))

        # Save summary files
        for file_path in summary_result['output_files']:
            filename = os.path.basename(file_path)
            shutil.copy2(file_path, os.path.join(output_dir, filename))

        # Mark job as completed
        job.mark_completed()
        update_job_progress(job_id, "Processing completed successfully!", 100)

        return {
            'status': 'completed',
            'output_files': [os.path.basename(f) for f in summary_result['output_files']],
            'transcript_file': f"{base_name}_{'diarized_' if diarization_result else ''}transcript.txt"
        }

    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        current_app.logger.error(f"Audio processing task failed for job {job_id}: {e}")

        if job:
            job.set_error(error_msg)

        raise self.retry(exc=e, countdown=60, max_retries=3)

    finally:
        # Cleanup temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                current_app.logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")


@celery.task(bind=True)
def process_transcript_task(self, job_id):
    """Process uploaded transcript file through summarization."""
    job = None
    temp_dir = None

    try:
        # Get job from database
        job = Job.query.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.PROCESSING
        db.session.commit()

        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"realrecap_job_{job_id}_")

        # Initialize processor
        summarization_processor = SummarizationProcessor(
            model_name=job.summarizer_model,
            ollama_host=current_app.config['OLLAMA_HOST']
        )

        # Get file paths
        input_file = os.path.join(current_app.config['UPLOAD_FOLDER'], job.input_file_path)
        output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], job.output_dir_path)

        # Process transcript
        update_job_progress(job_id, f"Processing transcript with {job.summarizer_model}...", 30)
        summary_result = summarization_processor.process_transcript(
            input_file,
            title=job.title,
            output_format=job.output_format
        )

        # Save results to output directory
        update_job_progress(job_id, "Saving results...", 80)
        for file_path in summary_result['output_files']:
            filename = os.path.basename(file_path)
            shutil.copy2(file_path, os.path.join(output_dir, filename))

        # Mark job as completed
        job.mark_completed()
        update_job_progress(job_id, "Processing completed successfully!", 100)

        return {
            'status': 'completed',
            'output_files': [os.path.basename(f) for f in summary_result['output_files']]
        }

    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        current_app.logger.error(f"Transcript processing task failed for job {job_id}: {e}")

        if job:
            job.set_error(error_msg)

        raise self.retry(exc=e, countdown=60, max_retries=3)

    finally:
        # Cleanup temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                current_app.logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")


@celery.task
def cleanup_expired_jobs():
    """Periodic task to clean up expired jobs."""
    try:
        from app.models import Job
        count = Job.cleanup_expired_jobs()
        current_app.logger.info(f"Cleaned up {count} expired jobs")
        return f"Cleaned up {count} expired jobs"
    except Exception as e:
        current_app.logger.error(f"Error in cleanup task: {e}")
        raise