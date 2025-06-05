#!/bin/bash

# Ollama Model Initialization Script
# Automatically downloads base models and creates custom models from Modelfiles

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="/tmp/models"
LOG_FILE="/tmp/ollama-init.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_info() {
    log "${BLUE}INFO:${NC} $1"
}

log_success() {
    log "${GREEN}SUCCESS:${NC} $1"
}

log_warning() {
    log "${YELLOW}WARNING:${NC} $1"
}

log_error() {
    log "${RED}ERROR:${NC} $1"
}

# Wait for Ollama service to be ready
wait_for_ollama() {
    log_info "Waiting for Ollama service to be ready..."
    local max_attempts=60
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if ollama list > /dev/null 2>&1; then
            log_success "Ollama service is ready"
            return 0
        fi
        
        log_info "Attempt $attempt/$max_attempts: Ollama not ready yet, waiting 5 seconds..."
        sleep 5
        ((attempt++))
    done
    
    log_error "Ollama service failed to start after $max_attempts attempts"
    return 1
}

# Check if a model exists
model_exists() {
    local model_name="$1"
    ollama list | grep -q "^$model_name"
}

# Download base model if not exists
download_base_model() {
    local model_name="$1"
    
    log_info "Checking base model: $model_name"
    
    if model_exists "$model_name"; then
        log_success "Base model $model_name already exists"
        return 0
    fi
    
    log_info "Downloading base model: $model_name (this may take a while...)"
    if ollama pull "$model_name"; then
        log_success "Successfully downloaded $model_name"
        return 0
    else
        log_error "Failed to download $model_name"
        return 1
    fi
}

# Create custom model from Modelfile
create_custom_model() {
    local model_name="$1"
    local modelfile_path="$2"
    
    log_info "Checking custom model: $model_name"
    
    if model_exists "$model_name"; then
        log_success "Custom model $model_name already exists"
        return 0
    fi
    
    if [ ! -f "$modelfile_path" ]; then
        log_error "Modelfile not found: $modelfile_path"
        return 1
    fi
    
    log_info "Creating custom model: $model_name from $modelfile_path"
    if ollama create "$model_name" -f "$modelfile_path"; then
        log_success "Successfully created custom model $model_name"
        return 0
    else
        log_error "Failed to create custom model $model_name"
        return 1
    fi
}

# Validate model functionality
validate_model() {
    local model_name="$1"
    local test_prompt="Hello, this is a test. Please respond with 'Model working correctly.'"
    
    log_info "Validating model: $model_name"
    
    local response
    if response=$(ollama run "$model_name" "$test_prompt" 2>/dev/null | head -n 1); then
        if [ -n "$response" ]; then
            log_success "Model $model_name validation passed"
            return 0
        else
            log_warning "Model $model_name responded but with empty output"
            return 1
        fi
    else
        log_error "Model $model_name validation failed"
        return 1
    fi
}

# Show system information
show_system_info() {
    log_info "=== System Information ==="
    log_info "GPU Info:"
    if command -v nvidia-smi >/dev/null 2>&1; then
        nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits | while read -r line; do
            log_info "  $line"
        done
    else
        log_warning "  nvidia-smi not available"
    fi
    
    log_info "Available Disk Space:"
    df -h /root/.ollama 2>/dev/null | tail -n 1 | awk '{print "  "$4" available"}' || log_warning "  Could not check disk space"
    
    log_info "Memory Info:"
    free -h | grep Mem | awk '{print "  "$3" used / "$2" total"}' || log_warning "  Could not check memory"
}

# Main execution
main() {
    log_info "=== Starting Ollama Model Initialization ==="
    
    # Show system information
    show_system_info
    
    # Wait for Ollama to be ready
    if ! wait_for_ollama; then
        log_error "Cannot proceed without Ollama service"
        exit 1
    fi
    
    # Track overall success
    local overall_success=true
    
    # Download base models
    log_info "=== Downloading Base Models ==="
    for base_model in "qwen3:14b" "qwen3:30b"; do
        if ! download_base_model "$base_model"; then
            overall_success=false
        fi
    done
    
    # Create custom models
    log_info "=== Creating Custom Models ==="
    
    # qwen3-summarizer:14b
    if ! create_custom_model "qwen3-summarizer:14b" "$MODELS_DIR/qwen3-summarizer-14b/Modelfile"; then
        overall_success=false
    fi
    
    # qwen3-summarizer:30b
    if ! create_custom_model "qwen3-summarizer:30b" "$MODELS_DIR/qwen3-summarizer-30b/Modelfile"; then
        overall_success=false
    fi
    
    # Validate models
    log_info "=== Validating Models ==="
    for model in "qwen3-summarizer:14b" "qwen3-summarizer:30b"; do
        if ! validate_model "$model"; then
            log_warning "Model $model failed validation but will continue"
        fi
    done
    
    # Final status
    log_info "=== Final Model Status ==="
    ollama list | tee -a "$LOG_FILE"
    
    if [ "$overall_success" = true ]; then
        log_success "=== Model initialization completed successfully ==="
        exit 0
    else
        log_error "=== Model initialization completed with some failures ==="
        exit 1
    fi
}

# Handle script termination
cleanup() {
    log_warning "Script interrupted, cleaning up..."
    exit 1
}

trap cleanup SIGINT SIGTERM

# Run main function
main "$@"