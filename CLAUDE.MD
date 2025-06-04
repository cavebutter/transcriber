# CLAUDE.MD - Development Handoff Notes

## Current Status: RealRecap Docker Deployment (95% Complete!)

**Context**: We've been implementing a dockerized Flask webapp that wraps transcription, diarization, and summarization CLI tools into a web interface with GPU support.

---

## ✅ WHAT'S WORKING:

### **System Setup:**
- **PopOS (Ubuntu 22.04)** with **RTX 4090** + **64GB RAM** + **i9**
- **Docker + Docker Compose** installed and working
- **NVIDIA Container Toolkit** installed and working
- **Host networking** solution implemented (Docker bridge networking failed)

### **Infrastructure:**
- **Redis**: Healthy and running
- **Ollama**: Running with **GPU detection working** (`nvidia-smi` shows RTX 4090)
- **Docker Images**: Built successfully (`transcriber2-webapp`)
- **GPU Access**: Tested and confirmed working with host networking

### **Docker Compose:**
- **docker-compose-host.yml**: Uses host networking (required due to bridge networking issues)
- **Environment files**: `.env` configured with real values
- **GPU allocation**: Single GPU queue design implemented (concurrency=1)

---

## 🚨 CURRENT BLOCKING ISSUE:

### **Flask CLI Command Error in run.py:**
```python
# Line ~214 in run.py - INCORRECT:
@app.cli.option('--force', is_flag=True, help='Force reimport existing models')

# Should be - CORRECT:
@click.option('--force', is_flag=True, help='Force reimport existing models')
```

**Error**: `AttributeError: 'AppGroup' object has no attribute 'option'`

### **Required Fix:**
1. Add `import click` to top of `run.py`
2. Change `@app.cli.option` to `@click.option` for the import-ollama-models command
3. Rebuild Docker image: `docker build -t transcriber2-webapp .`

---

## 🎯 IMMEDIATE NEXT STEPS:

### **1. Fix and Test Webapp (5 minutes):**
```bash
# Fix run.py, then:
docker build -t transcriber2-webapp .
docker run --rm --network=host -e GPU_AVAILABLE=true -it transcriber2-webapp
```
**Expected**: Flask app should start on port 5000

### **2. Deploy Full Stack (5 minutes):**
```bash
docker compose -f docker-compose-host.yml up -d
```
**Expected**: All services healthy, webapp accessible at http://localhost:5000

### **3. Import Ollama Models (if needed):**
```bash
# Check if models exist
curl http://localhost:11434/api/tags

# If empty, import from ollama-models/ directory
docker exec realrecap_ollama ollama create <model-name> -f /tmp/models/<model>/Modelfile
```

---

## 📋 ARCHITECTURE DECISIONS MADE:

### **GPU Strategy:**
- **Single GPU worker** (concurrency=1) to prevent conflicts
- **All GPU tasks routed through Celery** worker with GPU access
- **Ollama and Celery worker** both have GPU access but queue through Redis

### **Networking:**
- **Host networking** due to Docker bridge `veth` interface issues
- **All services on localhost** with different ports
- **No port conflicts** - confirmed Ollama on 11434, Redis on 6379

### **Service Dependencies:**
- **Webapp**: Waits for Redis + Ollama health checks
- **Celery Worker**: GPU-enabled, waits for Redis + Ollama
- **Celery Beat**: CPU-only, periodic tasks

---

## 🔧 KNOWN ISSUES & SOLUTIONS:

### **1. Docker Bridge Networking:**
- **Issue**: `failed to add veth interfaces: operation not supported`
- **Solution**: Using host networking (`network_mode: host`)

### **2. Celery Commands:**
- **Issue**: Module loading errors with `run:celery`
- **Solution**: Using `["celery", "-A", "run.celery", "worker"]` format

### **3. GPU Access:**
- **Issue**: Initially Ollama couldn't see GPU
- **Solution**: Added GPU device allocation to Ollama container

---

## 📁 KEY FILES:

### **Core Application:**
- `run.py` - **FIX NEEDED**: CLI command decorators
- `config.py` - Updated with GPU task routing
- `Dockerfile` - Ubuntu 22.04 base, working
- `docker-compose-host.yml` - Host networking version

### **Environment:**
- `.env` - Populated with real HF_TOKEN, SECRET_KEY, etc.
- `requirements-webapp.txt` - All dependencies working

---

## 🎯 USER'S GOALS:

### **Immediate:**
- Get proof-of-concept working locally
- Test full audio processing pipeline (upload → transcribe → diarize → summarize)

### **Future Architecture:**
- Separate web server from GPU processing server
- Web server handles UI/uploads, sends processing requests to GPU server
- This is the RIGHT approach for production scaling

---

## 🧪 TESTING CHECKLIST:

### **Once webapp starts:**
1. **Web Interface**: http://localhost:5000 loads
2. **Admin User**: Create admin account
3. **Audio Upload**: Test with files from `audio_samples/`
4. **GPU Processing**: Monitor `nvidia-smi` during processing
5. **Celery Tasks**: Check task queuing in Redis
6. **Output Generation**: Verify PDF generation works

### **Commands for monitoring:**
```bash
# Service status
docker compose -f docker-compose-host.yml ps

# Webapp logs
docker compose -f docker-compose-host.yml logs -f webapp

# GPU usage
watch -n 1 nvidia-smi

# Celery tasks
docker compose -f docker-compose-host.yml logs -f celery_worker
```

---

## 💡 DEBUGGING TIPS:

### **If services don't start:**
- Check logs: `docker compose -f docker-compose-host.yml logs <service>`
- Verify GPU access: `docker run --rm --network=host --gpus all ubuntu:22.04 ls /dev/nvidia*`
- Test Ollama: `curl http://localhost:11434/api/tags`

### **If webapp fails:**
- Test directly: `docker run --rm --network=host -it transcriber2-webapp`
- Check imports and CLI decorators in `run.py`
- Verify environment variables are set

---

## 🎉 SUCCESS CRITERIA:

**You'll know it's working when:**
1. All Docker services show "healthy" status
2. Webapp loads at http://localhost:5000
3. GPU is detected in startup logs
4. Can upload audio file and see processing progress
5. Generated PDF downloads successfully

**We're literally one `@click.option` fix away from a working system!**

---

## 📞 FINAL NOTES:

The user has been very patient and methodical. They understand Docker concepts well and have good debugging instincts. The infrastructure is solid - just need to fix that one CLI decorator bug and we should have a fully functional AI transcription webapp running on their RTX 4090.

The host networking approach works perfectly for their single-machine setup, and the GPU scheduling design will prevent resource conflicts. Once this proof-of-concept works, they want to architect a distributed version for production.

**Key insight**: This user thinks architecturally and wants to understand the system design, not just get things working. They'll appreciate explanations of why we made certain technical decisions.