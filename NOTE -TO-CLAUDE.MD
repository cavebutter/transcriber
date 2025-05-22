
Critical Context to Preserve:

Dependency Hell Solved: You fought through NumPy 2.x compatibility issues with PyTorch 2.2.0 - stick with NumPy 1.26.4
HF_TOKEN Management: Uses python-dotenv, validates early before processing starts
Temp File Cleanup: Implemented proper temp directory handling with automatic cleanup
Whisper Repetition Loops: Known issue that happens randomly - you decided to keep it simple for now rather than implement heavy detection

Docker-Specific Advice:

Multi-stage builds - Separate stages for dependencies vs runtime to keep image size manageable
CUDA base image - Use nvidia/cuda:12.1-runtime-ubuntu22.04 or similar for GPU support
System dependencies - Don't forget: ffmpeg, pandoc, texlive-xetex for PDF generation
Volume mounts - Plan for audio uploads, output downloads, and persistent temp storage
Environment variables - HF_TOKEN, model paths, output directories

Webapp Architecture Suggestions:

Async processing - Audio transcription takes time, use Celery/Redis or similar for background jobs
File size limits - Set reasonable limits on audio uploads
Progress tracking - WebSocket connections for real-time progress updates
Model caching - Whisper models are large, cache them in the container
Resource management - GPU memory cleanup between jobs is crucial

Code Quality Notes:

The transcribe.py improvements (better error handling, progress reporting, temp file management) are solid
The summarize.py prompts were just fixed - keep that recent work
Requirements-new.txt is clean and tested - use it as the Docker pip install base

Testing Strategy:

Test with various audio formats and lengths
Verify GPU utilization in container
Test the full pipeline: audio → transcription → diarization → summarization → PDF
Load testing with multiple concurrent jobs

Watch Out For:

PyAnnote.audio can be finicky in Docker - pin those versions exactly
CUDA version mismatches between host and container
File permissions for uploaded/generated files
Memory usage with large audio files + GPU models

Good luck with the webapp! The core functionality is solid - now you're just packaging it up nicely.