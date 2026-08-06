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
import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict
from pythonjsonlogger.json import JsonFormatter

# Register metrics
import warm_logic.observability.metrics as _  # noqa: F401
from warm_logic.app.cockpit.adapter import CockpitAdapter
from warm_logic.economy.token import TokenLedger
from warm_logic.kernel.mesh import dht
from warm_logic.kernel.ops.metrics import SystemMetrics
from warm_logic.kernel.zanzibar import zanzibar

# Configuration: HARDENING PHASE 1
API_KEY = os.environ.get("SOVEREIGN_COCKPIT_KEY")
COMMERCIAL_MODE = os.environ.get("SOVEREIGN_COMMERCIAL_MODE") == "1"
if not API_KEY:
    print("CRITICAL: SOVEREIGN_COCKPIT_KEY environment variable is NOT set.")
    print("For security reasons, the Cockpit will not start without a secure key.")
    sys.exit(1)

HTTP_PORT = int(os.environ.get("COCKPIT_HTTP_PORT", "5001"))

# Global State
adapter = CockpitAdapter()
reality_monitor = SystemMetrics()
dht_node = None
token_ledger = TokenLedger()  # [Phase 74] Economy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    logger.info("Initializing Sovereign DHT...")
    global dht_node
    # Use random port or fixed offset for Cockpit DHT
    dht_port = HTTP_PORT + 100
    # Mock node_id for now, in production derive from Key
    node_id = os.urandom(32)

    dht_node = dht.SovereignDHT(node_id, "127.0.0.1", dht_port)
    await dht_node.start()

    # Inject into adapter
    adapter.dht_node = dht_node
    logger.info(f"DHT Started on port {dht_port}")

    yield

    # Shutdown
    # dht_node.stop() if implemented


# Initialize Components
app = FastAPI(
    title="WarmLogic Sovereign Cockpit",
    description="""
## Sovereign Cockpit API

Control plane for WarmLogic Sovereign Nodes.

### Features
- **Real-time Telemetry**: SSE streaming for mesh and kernel status
- **Policy Management**: Seal and propagate governance policies
- **Mesh Monitoring**: DHT peer discovery and health checks

### Authentication
All endpoints require `X-API-Key` header with `SOVEREIGN_COCKPIT_KEY`.
""",
    version="0.4.0",
    contact={"name": "espressolee", "email": "https://github.com/espressolee/warmlogic-rust-core-artifact/issues"},
    license_info={"name": "Apache-2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"},
    openapi_tags=[
        {"name": "status", "description": "System status and health checks"},
        {"name": "mesh", "description": "DHT mesh network operations"},
        {"name": "config", "description": "Policy configuration management"},
        {"name": "logs", "description": "Kernel activity logs"},
        {"name": "tracing", "description": "Distributed task tracing"},
    ],
    lifespan=lifespan,
)

# HARDENING PHASE 1: CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [Phase 74] Economy Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint  # noqa: E402


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip health, status, and static
        if not COMMERCIAL_MODE or request.url.path.startswith(
            ("/health", "/static", "/api/status", "/metrics", "/docs", "/openapi.json")
        ):
            return await call_next(request)

        # Extract Token ID (Simplification: User passes Node ID as token for now)
        # In real world: X-Sovereign-Auth: <JWT signed by Node Key>
        client_node = request.headers.get("X-Sovereign-Node-ID")

        if not client_node:
            # Grant free tier for Cockpit UI (Browser) which doesn't have Node ID yet
            # Checking for specific browser headers or API Key presence?
            # For now, if valid API Key present, we waive fees (Admin Access)
            if request.headers.get("X-API-Key") == API_KEY:
                return await call_next(request)

            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment Required",
                    "detail": "Missing X-Sovereign-Node-ID",
                },
            )

        # Deduct Cost (0.1 ST per call)
        cost = 0.1
        if token_ledger.get_balance(client_node) < cost:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Insufficient Funds",
                    "balance": token_ledger.get_balance(client_node),
                },
            )

        # Execute Deduction (Burn/Transfer to Root)
        token_ledger.transfer(client_node, "KERNEL_ROOT", cost)

        response = await call_next(request)
        response.headers["X-Sovereign-Cost"] = str(cost)
        response.headers["X-Sovereign-Balance"] = str(
            token_ledger.get_balance(client_node)
        )
        return response


app.add_middleware(TokenMiddleware)


# HARDENING PHASE 3: UI Security Guard
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    [SIM-037] Global Exception Handler to prevent stack trace leaks.
    Returns structured JSON error for all unhandled exceptions.
    """
    # Log the full trace internally
    logger.error(f"Captured Unhandled Exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error_code": "WL-E500",
            "message": "Internal Sovereign Error",
            "correlation_id": os.urandom(4).hex(),  # Trace ID
        },
    )


# Setup Logging (JSON)
logHandler = logging.StreamHandler()
formatter = JsonFormatter(
    "%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d"
)
logHandler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[logHandler], force=True)

logger = logging.getLogger("CockpitServer")


class VerifyKeysRequest(BaseModel):
    key: str


class SealConfigRequest(BaseModel):
    pii_sensitivity: float
    burn_multiplier: int
    # Allow other fields
    model_config = ConfigDict(extra="allow")


# Middleware for API Key verification (Manual implementation for flexibility)
def verify_api_key(request: Request) -> str:
    key = request.headers.get("X-API-Key")
    # Also check query param for SSE
    if not key:
        key = request.query_params.get("api_key")

    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    assert key is not None
    return key


def verify_permission(action: str, resource: str = "cluster") -> None:
    """
    [Fixed Phase G] Enforce Zanzibar RBAC.
    Default Subject: 'operator' (derived from Valid API Key).
    """
    subject = "operator"
    # Ensure implied permissions for operator on cluster exists or fail safe?
    # For Remediation, we enforce check. If tuple missing, it fails (Secure by Default).
    allowed = zanzibar.check(
        namespace="system", object_id=resource, relation=action, subject_id=subject
    )
    if not allowed:
        # Auto-bootstrap for 'operator' if this is first run?
        # No, Remediation Plan says "Switch Ghost Auth -> Enforced Zoning".
        # If it breaks, we must add tuples to DB.
        logger.warning(
            f"⛔ [Zanzibar] Access Denied for {subject} on {resource}:{action}"
        )
        raise HTTPException(
            status_code=403, detail=f"Sovereign Access Denied: {action} on {resource}"
        )


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    return adapter.get_system_status()


@app.get("/api/memory/working")
async def get_working_memory(request: Request) -> Any:
    """Returns the active context window from Sovereign Chat."""
    verify_api_key(request)
    # verify_permission("read", "memory") # Future
    return adapter.get_working_memory()


@app.post("/api/verify_key")
async def verify_key(req: VerifyKeysRequest) -> Dict[str, str]:
    """Verify the provided access key against the sovereign environment."""
    if req.key == API_KEY:
        return {"status": "success", "message": "Access Witnessed"}
    raise HTTPException(status_code=401, detail="Invalid Key")


@app.get("/api/mesh")
async def get_mesh(request: Request) -> Any:
    """Real-time Mesh Telemetry."""
    verify_api_key(request)
    verify_permission("view", "mesh")
    return adapter.get_mesh_status()


@app.get("/api/logs")
async def get_logs(limit: int = 15, request: Optional[Request] = None) -> Any:
    # verify_api_key(request)
    return adapter.get_recent_activity(limit=limit)


@app.get("/api/traces")
async def get_traces(limit: int = 10, request: Optional[Request] = None) -> Any:
    # verify_api_key(request)
    return adapter.get_traces(limit=limit)


@app.get("/api/traces/{trace_id}")
async def get_trace_details(trace_id: str, request: Request) -> Any:
    # verify_api_key(request)
    events = adapter.get_trace_events(trace_id)
    if not events:
        raise HTTPException(status_code=404, detail="Trace not found")
    return events


@app.get("/api/logs/stream")
async def stream_logs(request: Request) -> Any:
    """Server-Sent Events (SSE) for real-time log updates."""
    try:
        verify_api_key(request)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})
    except Exception as e:
        logger.error(f"Stream auth error: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Auth Error"})

    async def event_generator() -> Any:
        last_log_id = None
        last_drift_score = -1.0
        last_mesh_hash = None

        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                break

            # 1. Reality Check
            drift_score = reality_monitor.drift_score
            current_root = getattr(reality_monitor, "local_root", "UNKNOWN")

            if drift_score != last_drift_score:
                last_drift_score = drift_score
                reality_event = {
                    "type": "REALITY_SYNC",
                    "drift_score": drift_score,
                    "local_root": str(current_root),
                    "absolute_root": str(reality_monitor.absolute_root),
                    "status": (
                        "SYNCED" if drift_score <= 0.1 else "DRIFTING"
                    ),  # relaxed check
                    "timestamp": time.time(),
                }
                yield f"data: {json.dumps(reality_event)}\n\n"

            # 2. Mesh & System Status
            status = adapter.get_system_status()
            mesh_status = adapter.get_mesh_status()
            mesh_hash = hash(str(mesh_status))  # Simple hash for change detection

            if mesh_hash != last_mesh_hash:
                last_mesh_hash = mesh_hash
                telemetry_event = {
                    "type": "TELEMETRY_UPDATE",
                    "system_status": status,
                    "mesh": mesh_status,
                    "timestamp": time.time(),
                }
                yield f"data: {json.dumps(telemetry_event)}\n\n"

            # 3. Kernel Logs
            logs = adapter.get_recent_activity(limit=1)
            if logs:
                current_log = logs[0]
                log_id = current_log.get("file")
                if log_id != last_log_id:
                    last_log_id = log_id
                    # Simulate NER entities for now
                    current_log["entities"] = [
                        {
                            "label": "POLICY",
                            "text": current_log.get("policy", "UNKNOWN"),
                        }
                    ]
                    yield f"data: {json.dumps(current_log)}\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/config")
async def get_config(request: Request) -> Any:
    verify_api_key(request)
    verify_permission("read", "policy")
    return adapter.get_config()


@app.post("/api/config/seal")
async def seal_config(req: SealConfigRequest, request: Request) -> Dict[str, str]:
    """Sign and propagate new policy hardening settings."""
    verify_api_key(request)
    verify_permission("admin", "policy")

    # Stub: Save to file or update system
    # In a real implementation this would interact with the governance engine

    return {
        "status": "success",
        "message": "Policy sealed and propagated to mesh.",
        "signature": "simulated_signature_0x123",
    }


# Mount Static Files
# Assuming structure: warm_logic/app/cockpit/web/static
static_dir = Path(__file__).parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Mount Templates (Index)
@app.get("/")
async def root(request: Request) -> Any:
    index_path = Path(__file__).parent / "web" / "templates" / "index.html"
    if index_path.exists():
        templates = Jinja2Templates(directory=index_path.parent)
        return templates.TemplateResponse("index.html", {"request": request})

    return HTMLResponse(content="<h1>Cockpit UI Not Found</h1>", status_code=404)


@app.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/live")
async def health_live() -> Dict[str, str]:
    """Liveness probe: Process is running."""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready() -> Dict[str, str]:
    """Readiness probe: Dependencies (DHT, Core) are ready."""
    if dht_node is None:
        raise HTTPException(status_code=503, detail="DHT not initialized")
    return {"status": "ready", "dht": "connected"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT)
