# WarmLogic Sovereign Node Dockerfile
# Global Fleet Deployment

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (Required for warm_logic_core and PQC)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Set workspace
WORKDIR /app

# Copy dependency files first
COPY pyproject.toml .
# Install dependencies (ignoring local dev deps)
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ ./src/
COPY configs/ ./configs/

# Create necessary directories
RUN mkdir -p /app/data/sovereign_db /app/logs

# Environment Variables
ENV PYTHONPATH="/app/src"
ENV SOVEREIGN_HOME="/app/data"
ENV SOVEREIGN_PORT=20000

# Expose DHT and RPC ports
EXPOSE 20000/udp
EXPOSE 20000/tcp
EXPOSE 8080/tcp

# Run the daemon
CMD ["python3", "-m", "warm_logic.daemon", "--config", "configs/default_node.json"]
