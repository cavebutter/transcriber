#!/bin/bash

# Ollama Container Entrypoint Script
# Starts Ollama service and initializes models in background

set -e

INIT_SCRIPT="/app/scripts/init-ollama-models.sh"
OLLAMA_READY_FILE="/tmp/ollama-models-ready"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[OLLAMA-ENTRYPOINT]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OLLAMA-ENTRYPOINT]${NC} $1"
}

# Start Ollama service in background
log_info "Starting Ollama service..."
ollama serve &
OLLAMA_PID=$!

# Function to cleanup on exit
cleanup() {
    log_info "Shutting down Ollama service..."
    kill $OLLAMA_PID 2>/dev/null || true
    wait $OLLAMA_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Initialize models in background
log_info "Starting model initialization in background..."
(
    # Give Ollama a moment to start
    sleep 10
    
    # Run model initialization
    if [ -x "$INIT_SCRIPT" ]; then
        log_info "Running model initialization script..."
        if "$INIT_SCRIPT"; then
            log_success "Model initialization completed successfully"
            touch "$OLLAMA_READY_FILE"
        else
            log_info "Model initialization completed with some issues, but continuing..."
            touch "$OLLAMA_READY_FILE"
        fi
    else
        log_info "Model initialization script not found or not executable: $INIT_SCRIPT"
        log_info "Models will need to be created manually"
        touch "$OLLAMA_READY_FILE"
    fi
) &

# Wait for Ollama service to finish
log_info "Ollama service is running (PID: $OLLAMA_PID)"
log_info "Model initialization is running in background..."
log_info "Use 'docker logs realrecap_ollama' to monitor progress"

wait $OLLAMA_PID