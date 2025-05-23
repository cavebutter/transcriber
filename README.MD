# RealRecap - AI-Powered Meeting Transcription & Summarization

A comprehensive webapp that transforms audio recordings and transcripts into actionable meeting summaries using cutting-edge AI technologies.

## ✨ Features

- **High-Accuracy Transcription**: Uses OpenAI Whisper for speech-to-text conversion
- **Speaker Identification**: Advanced speaker diarization with PyAnnote.audio
- **AI Summarization**: Custom fine-tuned models for meeting-specific summaries
- **Multi-Format Support**: Audio files (WAV, MP3, M4A, etc.) and text transcripts
- **Real-Time Progress**: WebSocket-based progress tracking
- **Professional Reports**: Generate PDF, HTML, and Markdown outputs
- **User Management**: Secure authentication and file management
- **Background Processing**: Celery-based async task processing
- **Docker Support**: Complete containerized deployment

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Redis server
- Ollama (for AI summarization)
- System dependencies: `ffmpeg`, `pandoc`, `texlive-xetex`

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd realrecap-webapp
   ```

2. **Run the setup script**
   ```bash
   python setup.py
   ```
   This will:
   - Check dependencies
   - Install Python packages
   - Set up environment configuration
   - Initialize the database
   - Import Ollama models
   - Create an admin user

3. **Configure environment**
   Edit `.env` file with your settings:
   ```env
   HF_TOKEN=your_huggingface_token_here
   SECRET_KEY=your-secret-key
   OLLAMA_HOST=http://localhost:11434
   ```

4. **Start services**
   ```bash
   # Terminal 1: Start Redis
   redis-server
   
   # Terminal 2: Start Ollama
   ollama serve
   
   # Terminal 3: Start Celery worker
   celery -A run.celery worker --loglevel=info
   
   # Terminal 4: Start Flask app
   python run.py
   ```

5. **Access the application**
   Open http://localhost:5000 in your browser

## 🐳 Docker Deployment

For production deployment with Docker:

1. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

This will start:
- Flask webapp
- Celery worker
- Redis
- Ollama with GPU support

## 📋 Usage

### Processing Audio Files

1. **Upload Audio**: Select or drag-and-drop audio files (WAV, MP3, M4A, etc.)
2. **Configure Options**:
   - Whisper model (tiny to large)
   - Summarizer model (14B or 30B)
   - Speaker diarization settings
   - Output format (PDF, HTML, Markdown)
3. **Start Processing**: Jobs run in background with real-time progress
4. **Download Results**: Get transcripts and professional summaries

### Processing Existing Transcripts

1. **Upload Transcript**: Support for plain text and Microsoft Teams transcripts (.docx)
2. **Select Model**: Choose summarization model
3. **Generate Summary**: AI creates executive summaries and key points
4. **Download Results**: Professional formatted reports

## 🏗️ Architecture

### Core Components

- **Flask Application**: Web interface and API endpoints
- **Celery Workers**: Background task processing
- **Redis**: Message broker and result storage
- **SQLite/PostgreSQL**: User and job data storage
- **Ollama**: Local LLM inference server

### Processing Pipeline

1. **Audio Upload** → **Format Conversion** (ffmpeg)
2. **Speech-to-Text** (Whisper) → **Speaker Diarization** (PyAnnote)
3. **AI Summarization** (Custom Ollama models) → **Report Generation** (LaTeX/Pandoc)

### File Structure

```
realrecap-webapp/
├── app/                    # Flask application
│   ├── auth/              # Authentication blueprint
│   ├── main/              # Main application routes
│   ├── api/               # API endpoints
│   ├── utils/             # Processing utilities
│   └── templates/         # HTML templates
├── static/                # CSS, JS, images
├── uploads/               # User file storage
├── ollama-models/         # Custom AI models
├── docker-compose.yml     # Docker orchestration
├── Dockerfile            # Container definition
└── requirements-webapp.txt # Python dependencies
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment mode | `development` |
| `SECRET_KEY` | Flask secret key | Required |
| `HF_TOKEN` | HuggingFace token (for diarization) | Required |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `DATABASE_URL` | Database connection | SQLite |
| `CELERY_BROKER_URL` | Redis broker URL | `redis://localhost:6379/0` |

### Model Configuration

The application uses custom Ollama models optimized for meeting transcription:

- **qwen3-summarizer:14b**: Faster processing, good quality
- **qwen3-summarizer:30b**: Slower processing, higher quality

Models are defined in `ollama-models/` directory with custom prompts for:
- Executive summary generation
- Key discussion points extraction
- Action item identification
- Risk highlighting

## 🛠️ Development

### Local Development Setup

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements-webapp.txt
   ```

3. **Set up pre-commit hooks** (optional)
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Running Tests

```bash
pytest tests/
```

### Database Migrations

```bash
# Initialize database
flask init-db

# Create admin user
flask create-admin
```

## 🚀 Production Deployment

### System Requirements

- **Minimum**: 8GB RAM, 4 CPU cores, 50GB storage
- **Recommended**: 16GB+ RAM, 8+ CPU cores, GPU for faster processing
- **GPU Support**: NVIDIA GPU with CUDA for optimal performance

### Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure PostgreSQL database
- [ ] Set up reverse proxy (nginx)
- [ ] Configure SSL certificates
- [ ] Set up monitoring (logs, metrics)
- [ ] Configure backup strategy
- [ ] Test file upload limits
- [ ] Verify GPU access in containers

## 📊 Monitoring and Maintenance

### Health Checks

The application provides health check endpoints:

- `/api/system/health` - Overall system status
- `/api/system/stats` - Usage statistics

### Log Management

Logs are stored in:
- `logs/realrecap.log` - Application logs
- Docker logs: `docker-compose logs webapp`

### Cleanup

Expired jobs are automatically cleaned up every hour. Manual cleanup:

```bash
# Clean up expired jobs
flask clean-expired-jobs
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues

**Issue**: Ollama models not loading
- **Solution**: Check model files in `ollama-models/` and run `flask import-ollama-models`

**Issue**: Speaker diarization fails
- **Solution**: Verify `HF_TOKEN` is set and accept PyAnnote terms on HuggingFace

**Issue**: PDF generation fails
- **Solution**: Ensure `pandoc` and `texlive-xetex` are installed

**Issue**: High memory usage
- **Solution**: Reduce Celery concurrency or use smaller Whisper models

### Getting Help

- Check the logs: `logs/realrecap.log`
- Review Docker logs: `docker-compose logs`
- Verify system dependencies
- Check Redis and Ollama connectivity

### Performance Optimization

- Use GPU for Whisper and PyAnnote processing
- Adjust Celery worker concurrency based on available resources
- Use smaller models for faster processing
- Implement file compression for large audio files
- Consider using PostgreSQL for better performance at scale

## 🔮 Roadmap

- [ ] Real-time audio streaming processing
- [ ] Multi-language support
- [ ] Custom model fine-tuning interface
- [ ] Integration with calendar applications
- [ ] Advanced analytics and insights
- [ ] Mobile application
- [ ] API for third-party integrations