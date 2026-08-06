# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
WarmLogic REST API Gateway - Main Application

FastAPI application providing external REST API for:
- Governance: Policy evaluation and decision proposals
- Evidence: Cryptographic proof retrieval and verification
- Consensus: BFT status and network health
- Crypto: Post-quantum signature operations

Port: 8000 (default)
Authentication: API Key (X-API-Key header)
"""

import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

# Import routers
from warm_logic.gateway.routes import consensus, crypto, evidence, governance, mesh

# Configuration
API_KEY = os.environ.get("WARMLOGIC_API_KEY", os.environ.get("SOVEREIGN_COCKPIT_KEY"))
GATEWAY_PORT = int(os.environ.get("WARMLOGIC_GATEWAY_PORT", "8000"))

# SEC-006: Debug mode with production guard
_debug_requested = os.environ.get("WARMLOGIC_DEBUG", "0") == "1"
_is_production = os.environ.get("ENVIRONMENT", "").lower() == "production"
DEBUG_MODE = _debug_requested and not _is_production

if _debug_requested and _is_production:
    import warnings

    warnings.warn(
        "SEC-006: WARMLOGIC_DEBUG=1 ignored in production environment. "
        "Set ENVIRONMENT to non-production to enable debug mode.",
        RuntimeWarning,
        stacklevel=1,
    )

# Metrics
REQUEST_COUNT = Counter(
    "warmlogic_gateway_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "warmlogic_gateway_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)

# Logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WarmLogic.Gateway")


# Global state for Rust Core
_rust_core_ready = False
_rust_core_exports = 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    global _rust_core_ready, _rust_core_exports

    logger.info("WarmLogic Gateway starting...")
    logger.info(f"Port: {GATEWAY_PORT}")
    logger.info(f"Debug: {DEBUG_MODE}")
    logger.info(f"API Key configured: {'Yes' if API_KEY else 'No (WARNING!)'}")

    # [P3] Initialize Rust Core (warm_logic_rs)
    try:
        import warm_logic_rs as rs

        exports = [x for x in dir(rs) if not x.startswith("_")]
        _rust_core_exports = len(exports)

        # Verify critical modules
        required = [
            "PQCKeypair",
            "MLDSA",
            "RustZKProofGenerator",
            "BFTEngine",
            "ReflectiveLoop",
        ]
        missing = [m for m in required if not hasattr(rs, m)]
        if missing:
            logger.warning(f"Rust Core missing modules: {missing}")
            _rust_core_ready = False
        else:
            _rust_core_ready = True
            logger.info(
                f"✅ Rust Core initialized: {_rust_core_exports} exports, all critical modules present"
            )
    except ImportError as e:
        logger.error(f"Rust Core (warm_logic_rs) not available: {e}")
        logger.error(
            "Run: cd warm_logic_rs && maturin develop --release --features 'python,std,persistence'"
        )
        _rust_core_ready = False

    yield

    # Shutdown
    logger.info("WarmLogic Gateway shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="WarmLogic REST API Gateway",
        description="""
## WarmLogic REST API Gateway

External REST API for WarmLogic AI governance Governance.

### Features

- **Governance**: Propose actions, evaluate policies, manage rules
- **Evidence**: Retrieve and verify cryptographic proofs
- **Consensus**: Monitor BFT network status
- **Crypto**: Post-quantum signature operations

### Authentication

All endpoints require `X-API-Key` header with valid API key.

### research prototype Notice

This is a research prototype. APIs may change before v1.0 release.

### Post-Quantum Security

All cryptographic operations use ML-DSA-65 (FIPS 204) for quantum resistance.
""",
        version="0.1.0",
        contact={
            "name": "espressolee",
            "email": "70549809+espressolee@users.noreply.github.com",
            "url": "https://github.com/espressolee/WarmLogic",
        },
        license_info={
            "name": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0",
        },
        openapi_tags=[
            {
                "name": "governance",
                "description": "AI governance and policy operations",
            },
            {
                "name": "evidence",
                "description": "Cryptographic evidence and audit trails",
            },
            {
                "name": "consensus",
                "description": "BFT consensus network status",
            },
            {
                "name": "crypto",
                "description": "Post-quantum cryptographic operations",
            },
            {
                "name": "health",
                "description": "Health checks and metrics",
            },
        ],
        lifespan=lifespan,
    )

    # CORS Middleware - SEC-002: Require explicit origins, no wildcards
    cors_origins = os.environ.get("WARMLOGIC_CORS_ORIGINS", "")
    if not cors_origins or cors_origins == "*":
        # In production, require explicit origins for security
        # Default to localhost only for development
        cors_origins = (
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000"
        )
        logger.warning(
            "WARMLOGIC_CORS_ORIGINS not set or set to wildcard. "
            "Defaulting to localhost only. Set explicit origins for production."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type", "Authorization"],
    )

    # Request timing middleware
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next: Any) -> Response:
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        # Record metrics
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(process_time)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
        ).inc()

        return response

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle uncaught exceptions without leaking stack traces."""
        correlation_id = os.urandom(4).hex()
        # SEC-006: Only log stack traces in debug mode to prevent info disclosure
        logger.error(
            f"Unhandled exception [correlation_id={correlation_id}]: {exc}",
            exc_info=DEBUG_MODE,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An internal error occurred",
                "correlation_id": correlation_id,
            },
        )

    # Include routers
    app.include_router(governance.router, prefix="/api/v1", tags=["governance"])
    app.include_router(evidence.router, prefix="/api/v1", tags=["evidence"])
    app.include_router(consensus.router, prefix="/api/v1", tags=["consensus"])
    app.include_router(crypto.router, prefix="/api/v1", tags=["crypto"])
    app.include_router(mesh.router, prefix="/api/v1", tags=["mesh"])

    # Health endpoints
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """Basic health check."""
        return {
            "status": "healthy",
        }

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict:
        """Kubernetes liveness probe."""
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict:
        """Kubernetes readiness probe - checks Rust Core availability."""
        checks = {
            "rust_core": _rust_core_ready,
            "rust_core_exports": _rust_core_exports,
        }
        all_ready = all([_rust_core_ready])
        return {
            "status": "ready" if all_ready else "degraded",
            "checks": checks,
        }

    @app.get("/metrics", tags=["health"])
    async def metrics() -> Response:
        """Prometheus metrics endpoint."""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "name": "WarmLogic REST API Gateway",
            "version": "0.1.0",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
        }

    return app


# Create default app instance
gateway_app = create_app()


def verify_api_key(request: Request) -> str:
    """Verify API key from request headers.

    Security: API key must be provided in X-API-Key header only.
    Query parameters are NOT supported to prevent key exposure in logs.
    """
    # SEC-003: Only accept API key from headers, never query params
    key = request.headers.get("X-API-Key")

    # SEC-001: Require API key in all environments (no development bypass)
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "configuration_error",
                "message": "API key not configured. Set WARMLOGIC_API_KEY environment variable.",
            },
        )

    # SEC-007: Use constant-time comparison to prevent timing attacks
    if not key or not secrets.compare_digest(key, API_KEY):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Invalid or missing API key. Provide X-API-Key header.",
            },
        )
    return key


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(gateway_app, host="0.0.0.0", port=GATEWAY_PORT)
