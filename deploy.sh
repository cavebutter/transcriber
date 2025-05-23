#!/bin/bash
# RealRecap Docker Deployment Script

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

# Check for NVIDIA Docker (for GPU support)
check_nvidia_docker() {
    log_info "Checking for NVIDIA Docker support..."

    if command -v nvidia-smi &> /dev/null && docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
        log_success "NVIDIA Docker support detected"
        return 0
    else
        log_warning "NVIDIA Docker support not detected. GPU acceleration will not be available."
        return 1
    fi
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

    # Check for required environment variables
    if ! grep -q "HF_TOKEN=" .env || grep -q "HF_TOKEN=your_huggingface_token_here" .env; then
        log_warning "HF_TOKEN not set in .env file. Speaker diarization will not work."
    fi

    if ! grep -q "SECRET_KEY=" .env || grep -q "SECRET_KEY=.*change.*" .env; then
        log_warning "SECRET_KEY should be changed for production deployment"
    fi
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p uploads
    mkdir -p logs

    # Set permissions
    chmod 755 uploads logs

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
    max_attempts=30
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if $DOCKER_COMPOSE_CMD exec ollama ollama list &> /dev/null; then
            break
        fi
        sleep 2
        ((attempt++))
    done

    if [[ $attempt -eq $max_attempts ]]; then
        log_error "Ollama failed to start"
        return 1
    fi

    log_success "Ollama is ready"

    # Import models
    for model_dir in ollama-models/*/; do
        if [[ -d "$model_dir" && -f "$model_dir/Modelfile" ]]; then
            model_name=$(basename "$model_dir")
            log_info "Importing model: $model_name"

            $DOCKER_COMPOSE_CMD exec ollama sh -c "cd /tmp/models/$model_name && ollama create $model_name -f Modelfile"

            if [[ $? -eq 0 ]]; then
                log_success "Successfully imported $model_name"
            else
                log_error "Failed to import $model_name"
            fi
        fi
    done
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
    max_attempts=60
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if curl -f http://localhost:5000/api/system/health &> /dev/null; then
            log_success "Webapp is ready"
            break
        fi
        sleep 2
        ((attempt++))

        if [[ $((attempt % 10)) -eq 0 ]]; then
            log_info "Still waiting for webapp to start... (${attempt}s)"
        fi
    done

    if [[ $attempt -eq $max_attempts ]]; then
        log_error "Webapp failed to start within timeout"
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
    echo "  📊 Redis: localhost:6379"

    echo ""
    log_info "Useful commands:"
    echo "  📋 View logs: $DOCKER_COMPOSE_CMD logs -f webapp"
    echo "  🔄 Restart: $DOCKER_COMPOSE_CMD restart"
    echo "  🛑 Stop: $DOCKER_COMPOSE_CMD down"
    echo "  🗑️  Clean up: $DOCKER_COMPOSE_CMD down -v"
}

# Main deployment function
main() {
    echo "🎯 RealRecap Docker Deployment"
    echo "================================"

    # Pre-flight checks
    check_docker
    check_docker_compose
    GPU_SUPPORT=$(check_nvidia_docker && echo "true" || echo "false")

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
    fi

    # Start all services
    start_services

    # Wait for services
    if wait_for_services; then
        log_success "Deployment completed successfully!"
        show_status
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
        $DOCKER_COMPOSE_CMD logs -f webapp
        ;;
    "status")
        show_status
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
        echo "Usage: $0 [start|stop|restart|logs|status|clean]"
        echo ""
        echo "Commands:"
        echo "  start   - Start existing deployment"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  logs    - Show webapp logs"
        echo "  status  - Show service status"
        echo "  clean   - Remove all containers and volumes"
        echo ""
        echo "Run without arguments for full deployment"
        exit 1
        ;;
esac