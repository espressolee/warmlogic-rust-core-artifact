#!/bin/bash
# Sovereign Intelligence - llama.cpp RVV v1.0 Deployment
# Target: VisionFive 2 (JH7110)

echo "🚀 Preparing llama.cpp with RVV v1.0 for VisionFive 2..."

# 1. Clone (if not exists)
if [ ! -d "external/llama.cpp" ]; then
    mkdir -p external
    git clone https://github.com/ggerganov/llama.cpp external/llama.cpp
fi

cd external/llama.cpp

# 2. Build Configuration
# JH7110 supports RVV v1.0 (some early chips v0.7.1, but v1.0 is the standard for 2024+ images)
# We use LLAMA_RVV=ON and specify the target architecture.

mkdir -p build && cd build

echo "🛠️ Configuring CMake for RISC-V Vector..."

# Note: For native building on VisionFive 2
cmake .. \
    -DLLAMA_RVV=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="-march=rv64gcv" \
    -DCMAKE_CXX_FLAGS="-march=rv64gcv"

# 3. Instruction for Scribe
echo "---------------------------------------------------"
echo "✅ Configuration Complete."
echo "👉 Run 'make -j4' on the VisionFive 2 to finalize."
echo "👉 Use 'main -m models/tinyllama-1.1b.Q4_K_M.gguf -p \"Sovereign Protocol:\"' to test."
echo "---------------------------------------------------"
