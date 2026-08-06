# WarmLogic Rust Core - Production Dockerfile
# Multi-stage build for minimal image size and security

# ==============================================================================
# Stage 1: Build
# ==============================================================================
FROM rust:1.77-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy manifests first for dependency caching
COPY Cargo.toml Cargo.lock ./

# Create dummy src for dependency compilation
RUN mkdir src && \
    echo "fn main() {}" > src/main.rs && \
    echo "pub fn dummy() {}" > src/lib.rs

# Build dependencies only (for caching)
RUN cargo build --release --features std && \
    rm -rf src

# Copy actual source code
COPY src ./src
COPY benches ./benches

# Build release binary
RUN touch src/lib.rs && \
    cargo build --release --features std

# ==============================================================================
# Stage 2: Runtime
# ==============================================================================
FROM debian:bookworm-slim AS runtime

# Security: Run as non-root user
RUN groupadd -r warmlogic && \
    useradd -r -g warmlogic -d /app -s /sbin/nologin warmlogic

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/target/release/libwarm_logic_rs.so /app/
COPY --from=builder /build/target/release/libwarm_logic_rs.rlib /app/

# Copy configuration (if any)
# COPY config /app/config

# Security: Set ownership
RUN chown -R warmlogic:warmlogic /app

# Security: Drop all capabilities
USER warmlogic

# Labels
LABEL org.opencontainers.image.title="WarmLogic Rust Core"
LABEL org.opencontainers.image.description="Post-quantum cryptographic runtime for verifiable AI governance"
LABEL org.opencontainers.image.version="1.0.1"
LABEL org.opencontainers.image.vendor="WarmLogic"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.source="https://github.com/espressolee/WarmLogic"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD test -f /app/libwarm_logic_rs.so || exit 1

# No default command - this is a library
CMD ["echo", "WarmLogic Rust Core v1.0.1 - Use as library dependency"]

# ==============================================================================
# Stage 3: Python Bindings (optional)
# ==============================================================================
FROM python:3.12-slim-bookworm AS python

# Security: Run as non-root user
RUN groupadd -r warmlogic && \
    useradd -r -g warmlogic -d /app -s /sbin/nologin warmlogic

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /build

# Copy source
COPY . .

# Install maturin and build wheel
RUN pip install maturin && \
    maturin build --release --features python

# Final Python image
FROM python:3.12-slim-bookworm AS python-runtime

RUN groupadd -r warmlogic && \
    useradd -r -g warmlogic -d /app -s /sbin/nologin warmlogic

WORKDIR /app

# Copy wheel and install
COPY --from=python /build/target/wheels/*.whl /tmp/
RUN pip install /tmp/*.whl && rm -rf /tmp/*.whl

# Security
USER warmlogic

# Verify installation
RUN python -c "import warm_logic_rs; print('WarmLogic Rust Core loaded successfully')"

CMD ["python"]
