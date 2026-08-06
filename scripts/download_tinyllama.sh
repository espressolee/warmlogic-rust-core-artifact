#!/bin/bash
# Model Acquisition

MODEL_DIR="models"
MODEL_FILE="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
URL="https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

mkdir -p $MODEL_DIR

if [ -f "$MODEL_DIR/$MODEL_FILE" ]; then
    echo "✅ Model already exists at $MODEL_DIR/$MODEL_FILE"
else
    echo "📥 Downloading TinyLlama-1.1B (int4) for Sovereign Intelligence..."
    curl -L $URL -o "$MODEL_DIR/$MODEL_FILE"
fi
