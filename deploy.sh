#!/bin/bash
# RealRecap Docker Deployment Script - Updated for GPU Scheduling

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed and running
check_docker() {
    log_info "Checking Docker installation..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker and try again."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi

    log_success "Docker is installed and running"
}

# Check if Docker Compose is available
check_docker_compose() {
    log_info "Checking Docker Compose..."

    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif docker-compose --version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        log_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi

    log_success "Docker Compose is available"
}

# Check for NVIDIA Docker (REQUIRED for this app)
check_nvidia_docker() {
    log_info "Checking for NVIDIA Docker support (REQUIRED)..."

    if ! command -v nvidia-smi &> /dev/null; then
        log_error "nvidia-smi not found. Please install NVIDIA drivers."
        return 1
    fi

    # Check if nvidia-container-runtime is installed
    if ! docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi &> /dev/null; then
        log_error "NVIDIA Docker support not available. Please install nvidia-container-toolkit."
        echo "  Installation guide: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
        return 1
    fi

    # Get GPU info
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | head -1)
    log_success "NVIDIA Docker support detected"
    log_info "GPU: $GPU_INFO"
    return 0
}

# Set up environment file
setup_environment() {
    log_info "Setting up environment configuration..."

    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            log_success "Created .env file from template"
            log_warning "Please edit .env file with your configuration before continuing"

            # Prompt user to edit .env
            read -p "Press Enter after editing .env file, or Ctrl+C to exit..."
        else
            log_error ".env.example file not found. Cannot create environment configuration."
            exit 1
        fi
    else
        log_success "Environment file (.env) already exists"
    fi

    # Validate required environment variables
    source .env

    if [[ -z "$HF_TOKEN" || "$HF_TOKEN" == "your_huggingface_token_here" ]]; then
        log_warning "HF_TOKEN not set in .env file. Speaker diarization will not work."
        log_info "You can get a token from: https://huggingface.co/settings/tokens"
        log_info "Make sure to accept terms at: https://huggingface.co/pyannote/speaker-diarization-3.1"
    fi

    if [[ -z "$SECRET_KEY" || "$SECRET_KEY" == *"change"* ]]; then
        log_warning "SECRET_KEY should be changed for production deployment"
        # Generate a random secret key
        RANDOM_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        log_info "Suggested SECRET_KEY: $RANDOM_KEY"
    fi

    # Validate GPU_AVAILABLE setting
    if [[ "${GPU_AVAILABLE:-true}" == "true" ]]; then
        log_info "GPU processing enabled in configuration"
    else
        log_warning "GPU processing disabled in configuration"
    fi
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p uploads logs
    chmod 755 uploads logs

    # Create subdirectories for better organization
    mkdir -p uploads/temp
    mkdir -p logs/celery

    log_success "Directories created"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."

    $DOCKER_COMPOSE_CMD build

    log_success "Docker images built successfully"
}

# Import Ollama models
import_ollama_models() {
    log_info "Importing Ollama models..."

    if [[ ! -d "ollama-models" ]]; then
        log_error "ollama-models directory not found"
        return 1
    fi

    # Start Ollama service temporarily
    $DOCKER_COMPOSE_CMD up -d ollama

    # Wait for Ollama to be ready
    log_info "Waiting for Ollama to start..."
    max_attempts=60  # Increased timeout for model loading
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if $DOCKER_COMPOSE_CMD exec ollama ollama list &> /dev/null; then
            break
        fi
        sleep 2
        ((attempt++))

        if [[ $((attempt % 15)) -eq 0 ]]; then
            log_info "Still waiting for Ollama... (${attempt}s elapsed)"
        fi
    done

    if [[ $attempt -eq $max_attempts ]]; then
        log_error "Ollama failed to start within timeout"
        return 1
    fi

    log_success "Ollama is ready"

    # Import models using the CLI command
    $DOCKER_COMPOSE_CMD exec webapp python run.py import-ollama-models --timeout 600

    return $?
}

# Validate system requirements
validate_system() {
    log_info "Validating system requirements..."

    # Use the webapp container to run system validation
    $DOCKER_COMPOSE_CMD exec webapp python run.py validate-system

    return $?
}

# Start all services
start_services() {
    log_info "Starting all services..."

    $DOCKER_COMPOSE_CMD up -d

    log_success "All services started"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."

    # Wait for webapp
    max_attempts=120  # Increased for GPU service startup
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if curl -f http://localhost:5000/api/system/health &> /dev/null; then
            log_success "Webapp is ready"
            break
        fi
        sleep 2
        ((attempt++))

        if [[ $((attempt % 15)) -eq 0 ]]; then
            log_info "Still waiting for webapp to start... (${attempt}s elapsed)"
        fi
    done

    if [[ $attempt -eq $max_attempts ]]; then
        log_error "Webapp failed to start within timeout"
        log_info "Check logs with: $DOCKER_COMPOSE_CMD logs webapp"
        return 1
    fi
}

# Show status
show_status() {
    log_info "Service status:"
    $DOCKER_COMPOSE_CMD ps

    echo ""
    log_info "Application URLs:"
    echo "  🌐 Webapp: http://localhost:5000"
    echo "  🤖 Ollama: http://localhost:11434"

    # Only show Redis if exposed (development mode)
    if docker port realrecap_redis 6379 &> /dev/null; then
        echo "  📊 Redis: localhost:6379"
    fi

    echo ""
    log_info "Useful commands:"
    echo "  📋 View logs: $DOCKER_COMPOSE_CMD logs -f webapp"
    echo "  📋 View worker logs: $DOCKER_COMPOSE_CMD logs -f celery_worker"
    echo "  🔄 Restart: $DOCKER_COMPOSE_CMD restart"
    echo "  🛑 Stop: $DOCKER_COMPOSE_CMD down"
    echo "  🗑️  Clean up: $DOCKER_COMPOSE_CMD down -v"
    echo "  🔍 System check: $DOCKER_COMPOSE_CMD exec webapp python run.py validate-system"

    # Show GPU usage
    echo ""
    log_info "GPU Status:"
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader
    else
        echo "  nvidia-smi not available"
    fi
}

# Main deployment function
main() {
    echo "🎯 RealRecap Docker Deployment (GPU Optimized)"
    echo "================================================"

    # Pre-flight checks
    check_docker
    check_docker_compose

    # GPU check is REQUIRED for this application
    if ! check_nvidia_docker; then
        log_error "GPU support is required for RealRecap. Deployment failed."
        exit 1
    fi

    # Setup
    setup_environment
    create_directories

    # Build and deploy
    build_images

    # Start core services first
    log_info "Starting core services..."
    $DOCKER_COMPOSE_CMD up -d redis ollama

    # Import Ollama models
    if import_ollama_models; then
        log_success "Ollama models imported successfully"
    else
        log_warning "Some Ollama models failed to import"
        log_info "You can retry with: $DOCKER_COMPOSE_CMD exec webapp python run.py import-ollama-models"
    fi

    # Start all services
    start_services

    # Wait for services and validate
    if wait_for_services; then
        if validate_system; then
            log_success "Deployment completed successfully!"
            show_status
        else
            log_warning "Deployment completed but system validation failed"
            log_info "Check the issues above and retry validation"
            show_status
        fi
    else
        log_error "Deployment failed"
        log_info "Check logs with: $DOCKER_COMPOSE_CMD logs"
        exit 1
    fi

    echo ""
    log_success "🎉 RealRecap is now running!"
    echo "Visit http://localhost:5000 to get started"
}

# Handle script arguments
case "${1:-}" in
    "start")
        log_info "Starting existing deployment..."
        $DOCKER_COMPOSE_CMD up -d
        wait_for_services
        show_status
        ;;
    "stop")
        log_info "Stopping deployment..."
        $DOCKER_COMPOSE_CMD down
        log_success "Deployment stopped"
        ;;
    "restart")
        log_info "Restarting deployment..."
        $DOCKER_COMPOSE_CMD restart
        wait_for_services
        show_status
        ;;
    "logs")
        if [[ -n "${2:-}" ]]; then
            $DOCKER_COMPOSE_CMD logs -f "$2"
        else
            $DOCKER_COMPOSE_CMD logs -f webapp celery_worker
        fi
        ;;
    "status")
        show_status
        ;;
    "validate")
        log_info "Running system validation..."
        $DOCKER_COMPOSE_CMD exec webapp python run.py validate-system
        ;;
    "gpu")
        log_info "GPU Status:"
        if command -v nvidia-smi &> /dev/null; then
            nvidia-smi
        else
            log_error "nvidia-smi not available"
        fi
        ;;
    "clean")
        log_warning "This will remove all containers, networks, and volumes"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $DOCKER_COMPOSE_CMD down -v --remove-orphans
            docker system prune -f
            log_success "Cleanup completed"
        fi
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|logs [service]|status|validate|gpu|clean]"
        echo ""
        echo "Commands:"
        echo "  start     - Start existing deployment"
        echo "  stop      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  logs      - Show logs (optionally specify service)"
        echo "  status    - Show service status and GPU usage"
        echo "  validate  - Run system validation checks"
        echo "  gpu       - Show detailed GPU status"
        echo "  clean     - Remove all containers and volumes"
        echo ""
        echo "Run without arguments for full deployment"
        exit 1
        ;;
esac