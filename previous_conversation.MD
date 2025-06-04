I am taking this project to the next step by making it a dockerized webapp. All of the modules included work, though they are somewhat unpolished. I am comfortable using Flask as a framework, though I am open to suggestions. I believe that the webapp can be a single page with upload options for audio and diarized transcripts separately, along with inputs for all of the arguments for the modules.The file NOTE-TO-CLAUDE.MD is a note written specifically to you, Claude, from the instance of Claude that helped me through an earlier iteration. Please consider it as part of the help you provide me. Give me an overview of your recommended approach and confirm with me that I understand and agree before we move on to implementation.EditLooking at your codebase, I can see you have a solid audio transcription and meeting summarization pipeline. Based on the note from my previous instance and the code structure, here's my recommended approach for the dockerized webapp:
Webapp Architecture Overview
Framework: I recommend Flask since you're comfortable with it. For this use case, it's perfect - lightweight, well-suited for file uploads, and easy to integrate with your existing modules.
Core Design: Single-page application with two main workflows:

Audio Processing: Upload audio → transcribe → diarize → summarize → generate PDF
Transcript Processing: Upload existing transcript → summarize → generate PDF

Key Changes I Recommend
1. Async Processing with Progress Tracking

Use Celery + Redis for background jobs (audio transcription takes time)
WebSocket connections for real-time progress updates
Job queue management for handling multiple concurrent requests

2. File Management Refactoring

Centralized upload handling with size limits
Persistent storage for user files and outputs
Automatic cleanup of temporary files after job completion

3. Configuration Management

Environment-based config for Docker deployment
Separate dev/prod settings
Proper secrets management (HF_TOKEN, etc.)

4. Error Handling & User Experience

Graceful error handling with user-friendly messages
Input validation for all file types and parameters
Progress indicators and estimated completion times

5. Docker Multi-Stage Build

Base stage: CUDA runtime + system dependencies (ffmpeg, pandoc, texlive-xetex)
Dependencies stage: Python packages with the tested requirements-new.txt
Runtime stage: Your application code

Proposed File Structure
