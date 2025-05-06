#!/bin/bash

# === CONFIGURATION ===
MODEL="${1:-qwen3:14b}"              # Default to qwen3:14b if no argument is provided
LAYERS=30                            # Safe number of GPU layers to avoid VRAM exhaustion
SWAP_CHECK=true                      # Enable swap check
SWAPFILE="/swapfile"
SWAPSIZE="32G"

echo "🔧 Launching Ollama with model: $MODEL"
echo "🎛️  GPU layers: $LAYERS"

# === SWAP CHECK ===
if $SWAP_CHECK; then
    if ! swapon --show | grep -q "$SWAPFILE"; then
        echo "🧠 No swap file detected. Creating $SWAPSIZE swapfile at $SWAPFILE..."
        sudo fallocate -l "$SWAPSIZE" "$SWAPFILE"
        sudo chmod 600 "$SWAPFILE"
        sudo mkswap "$SWAPFILE"
        sudo swapon "$SWAPFILE"
        echo "✅ Swap enabled."
    else
        echo "🧠 Swap already active."
    fi
fi

# === ENVIRONMENT VARS ===
export OLLAMA_NUM_GPU_LAYERS="$LAYERS"

# === GPU Memory Snapshot (Before) ===
echo "📊 GPU usage before run:"
nvidia-smi

# === Run Ollama ===
echo "🚀 Starting Ollama with model: $MODEL..."
ollama run "$MODEL"

# === GPU Memory Snapshot (After) ===
echo "📊 GPU usage after run:"
nvidia-smi
