# WarmLogic Sovereign Node Dockerfile
# Production Multi-Node Deployment
#
# Build: docker build -t warmlogic/core:latest .
# Run:   docker run -p 8000:8000 warmlogic/core:latest

# Stage 1: Rust Builder
FROM python:3.12-slim AS rust-builder

WORKDIR /build

# Install Rust and maturin
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

# Install maturin
RUN pip install maturin

# Copy Rust source
COPY rust_core/ ./rust_core/

# Build Rust extension
WORKDIR /build/rust_core
RUN maturin build --release --features python

# Stage 2: Python Runtime
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r warmlogic && useradd -r -g warmlogic warmlogic

WORKDIR /app

# Copy Python source and requirements
COPY src/ ./src/
COPY requirements.txt .

# Copy Rust wheel from builder
COPY --from=rust-builder /build/rust_core/target/wheels/*.whl /tmp/

# Install dependencies (wheel from builder + requirements)
# Note: src/ is available via PYTHONPATH, no need for pip install .
RUN pip install --no-cache-dir /tmp/*.whl && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /tmp/*.whl

# Create directories
RUN mkdir -p /app/data /app/logs && \
    chown -R warmlogic:warmlogic /app

# Switch to non-root user
USER warmlogic

# Environment
ENV PYTHONPATH="/app/src"
ENV WARMLOGIC_DATA_DIR="/app/data"
ENV WARMLOGIC_LOG_DIR="/app/logs"
ENV WARMLOGIC_GATEWAY_PORT=8000
ENV ENVIRONMENT="production"

# Ports
EXPOSE 8000/tcp
EXPOSE 9000/udp
EXPOSE 9090/tcp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entry point - REST API Gateway
ENTRYPOINT ["python3", "-m", "warm_logic.gateway"]
