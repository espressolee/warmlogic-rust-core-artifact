# WarmLogic Production Dockerfile
# Multi-stage build for minimal image size

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (for PyO3 modules)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install maturin
RUN pip install maturin

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build Rust Core
COPY rust_core/ ./rust_core/
WORKDIR /app/rust_core
RUN maturin build --release --features 'python,std,persistence'
RUN pip install target/wheels/*.whl

# Production stage
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Run as non-root user
RUN useradd -m -u 1000 warmlogic
USER warmlogic

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
WORKDIR /app
COPY --chown=warmlogic:warmlogic src/ ./src/

# Environment variables
ENV PYTHONPATH=/app/src
ENV WARMLOGIC_ENV=production
ENV WARMLOGIC_LOG_LEVEL=INFO
ENV WARMLOGIC_GATEWAY_PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose Gateway API port
EXPOSE 8000

# Default command: Run Gateway
CMD ["python", "-m", "uvicorn", "warm_logic.gateway.app:gateway_app", "--host", "0.0.0.0", "--port", "8000"]
