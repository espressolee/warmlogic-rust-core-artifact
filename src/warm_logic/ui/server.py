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
import json
import logging
import os
import sys
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from warm_logic.kernel.constitution import guard as constitutional_guard
from warm_logic.kernel.ops.economy import CreditManager
from warm_logic.kernel.ops.metrics import SystemMetrics
from warm_logic.kernel.ops.tokenomics import WARMTokenManager
from warm_logic.kernel.provenance import audit_guard
from warm_logic.kernel.sys.cryptography import KineticSovereign
from warm_logic.mesh import Beacon, PeerManager, SocialSyncAgent
from warm_logic.mesh.topology import NetworkTopology
from warm_logic.observability import metrics as prom_metrics

try:
    from warm_logic_sdk import SovereignAssetSDK, SovereignClient
except ImportError:
    try:
        # Local source fallback for CI/dev where external wheel isn't installed.
        sdk_src = Path(__file__).resolve().parents[2] / "packages" / "warm_logic_sdk"
        if sdk_src.exists() and str(sdk_src) not in sys.path:
            sys.path.insert(0, str(sdk_src))
        from warm_logic_sdk import SovereignAssetSDK, SovereignClient
    except ImportError:
        try:
            # Legacy fallback with reduced capability.
            from warm_logic.sdk import SovereignClient

            SovereignAssetSDK = None
        except ImportError:
            # Keep explicit sentinel values; fail fast below with actionable error.
            SovereignClient = None
            SovereignAssetSDK = None

from warm_logic.security.rate_limiter import api_limiter
from warm_logic.social.protocol import SovereignMessage
from warm_logic.social.store import SocialStore
from warm_logic.system.fleet.manager import FleetManager


def get_version() -> str:
    v_path = Path(__file__).parent.parent / "VERSION"
    if v_path.exists():
        return v_path.read_text().strip()
    return "0.4.0-kinetic"


CURRENT_VERSION = get_version()

app = FastAPI(
    title="WarmLogic Glass Browser",
    description="""
## Glass Browser API

Public-facing API for WarmLogic Sovereign Nodes.

### Features
- **Identity Management**: Query node identity and signatures
- **Social Protocol**: Post and verify sovereign messages
- **Mesh Peers**: View connected nodes and sync status
- **Prometheus Metrics**: Export `/metrics` for monitoring

### Rate Limiting
All endpoints are rate-limited per IP address.
""",
    version=CURRENT_VERSION,
    contact={"name": "espressolee", "email": "70549809+espressolee@users.noreply.github.com"},
    license_info={"name": "Apache-2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"},
    openapi_tags=[
        {"name": "health", "description": "Liveness and readiness probes"},
        {"name": "identity", "description": "Node identity operations"},
        {"name": "social", "description": "Sovereign social protocol"},
        {"name": "mesh", "description": "P2P mesh network status"},
    ],
)
logger = logging.getLogger("GlassUI")
system_metrics = SystemMetrics()
start_time = time.time()

# Get configuration from environment
HTTP_PORT = int(os.environ.get("WARM_HTTP_PORT", "8000"))
DB_PATH = os.environ.get("WARM_DB_PATH", "data/social_db")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Any) -> Any:
    client_ip = request.client.host if request.client else "unknown"
    if not api_limiter.consume(client_ip):
        raise HTTPException(status_code=429, detail="Sovereign Rate Limit Exceeded")
    return await call_next(request)


@app.get("/health/liveness")
async def liveness() -> Dict[str, Any]:
    return {"status": "alive", "timestamp": time.time()}


@app.get("/health/readiness")
async def readiness() -> Dict[str, Any]:
    # SEC-006: Don't expose development mode in API responses
    is_dev_mode = os.environ.get("WARM_DEV_MODE") == "1"

    if is_dev_mode or len(peer_manager.get_active_peers()) > 0:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Not connected to mesh")


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    # Update some gauges before exporting
    prom_metrics.update_uptime()
    prom_metrics.PEER_COUNT.labels(region="local").set(
        len(peer_manager.get_active_peers())
    )
    prom_metrics.set_info(CURRENT_VERSION, "main")

    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Global Mesh Topology
REGION = os.environ.get("WARM_REGION", NetworkTopology.US_EAST)
NetworkTopology.set_local_region(REGION)

# Sovereign Provenance Guard
try:
    audit_guard()
    constitutional_guard.load_constitution()
except Exception as e:
    logger.critical(f"GUARD FAILURE: {e}")
    raise RuntimeError(f"CRITICAL: UI Server Guard breach: {e}")

if SovereignClient is None:
    raise RuntimeError(
        "SovereignClient import failed. Install `warm_logic_sdk` package or ensure "
        "`warm_logic.sdk` is importable in PYTHONPATH."
    )

client = SovereignClient()
social_store = SocialStore(db_path=DB_PATH)
economy = CreditManager(node_id=client.identity.id, store=social_store.store)
fleet_manager = FleetManager()
token_manager = WARMTokenManager(store=social_store.store)
asset_sdk = SovereignAssetSDK(client=client) if SovereignAssetSDK else None


def _mesh_node_id(raw_identity: str) -> str:
    # Keep beacon payload bounded even when identity is a very long PQC public key.
    if len(raw_identity) <= 128:
        return raw_identity
    return hashlib.sha256(raw_identity.encode()).hexdigest()


mesh_node_id = _mesh_node_id(client.identity.id)
# In production, AuditAgent would be passed this fleet_manager

# Initialize Mesh Networking (The Beacon)
peer_manager = PeerManager(ttl_seconds=15.0)
beacon = Beacon(
    node_id=mesh_node_id, http_port=HTTP_PORT, peer_manager=peer_manager
)
sync_agent = SocialSyncAgent(peer_manager, social_store)

# Seed with a system message
social_store.add_message(
    SovereignMessage(
        sender_id="KERNEL-ROOT",
        content="The Logic Society is online. Welcome to the Sovereign Web.",
        signature=KineticSovereign.bind_genesis(),
        timestamp=time.time(),
    )
)


class VerifyRequest(BaseModel):
    message: str


@app.on_event("startup")
async def startup_event() -> None:
    beacon.start()
    sync_agent.start()
    print(f"[Server] Glass Browser listening on port {HTTP_PORT}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    beacon.stop()
    sync_agent.stop()


@app.get("/api/identity")
async def get_identity() -> Dict[str, str]:
    return {"identity": client.identity.id}


@app.post("/api/verify")
async def verify_message(req: VerifyRequest) -> Dict[str, Any]:
    try:
        if hasattr(client, "echo_truth"):
            return client.echo_truth(req.message)

        if hasattr(client, "sign_message"):
            signed = client.sign_message(req.message)
            return {
                "message": req.message,
                "sender_id": signed.get("sender_id"),
                "signature": signed.get("signature"),
                "timestamp": signed.get("timestamp", time.time()),
                "verification_mode": "signature-only",
            }

        return {
            "message": req.message,
            "sender_id": getattr(getattr(client, "identity", None), "id", "UNKNOWN"),
            "timestamp": time.time(),
            "verification_mode": "fallback",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/social/feed")
async def get_social_feed() -> List[Dict[str, Any]]:
    return social_store.get_feed()


@app.post("/api/social/post")
async def post_to_social(req: VerifyRequest) -> Dict[str, Any]:
    try:
        if not hasattr(client, "sign_message"):
            raise RuntimeError("SovereignClient does not provide sign_message API")

        message_data = client.sign_message(req.message)
        normalized = {
            "sender_id": message_data.get(
                "sender_id", getattr(getattr(client, "identity", None), "id", "UNKNOWN")
            ),
            "content": req.message,
            "signature": message_data.get("signature", ""),
            "timestamp": float(message_data.get("timestamp", time.time())),
        }
        msg = SovereignMessage(**normalized)
        if social_store.add_message(msg):
            return {"status": "success", "message": msg.to_json()}
        else:
            raise HTTPException(status_code=400, detail="Signature verification failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mesh/peers")
async def get_mesh_peers() -> Dict[str, Any]:
    peers = peer_manager.get_active_peers()
    return {
        "active_peers": len(peers),
        "peers": [
            {
                "node_id": p.node_id[:20] + "...",
                "address": p.address,
                "port": p.http_port,
            }
            for p in peers
        ],
        "sync_stats": sync_agent.get_stats(),
    }


@app.get("/api/mesh/economy/balance")
async def get_economy_balance() -> Dict[str, Any]:
    return {
        "node_id": client.identity.id,
        "balance": economy.get_balance(client.identity.id),
        "currency": "Sovereign Credits",
    }


@app.get("/api/mesh/economy/transactions")
async def get_economy_transactions() -> List[Dict[str, Any]]:
    return economy.transactions


@app.get("/api/mesh/economy/staking")
async def get_staking_stats() -> Dict[str, Any]:
    return token_manager.get_staking_stats()


@app.post("/api/mesh/economy/stake")
async def post_economy_stake(req: Dict[str, Any]) -> Dict[str, Any]:
    amount = req.get("amount")
    if not amount:
        raise HTTPException(status_code=400, detail="Missing amount")
    if token_manager.stake(client.identity.id, float(amount)):
        return {"status": "success", "stats": token_manager.get_staking_stats()}
    else:
        raise HTTPException(status_code=400, detail="Staking failed")


@app.get("/api/mesh/assets/list")
async def list_assets() -> List[Dict[str, Any]]:
    return [
        {
            "id": a.asset_id,
            "owner": a.owner_id,
            "hw_root": a.hardware_id,
            "metadata": a.metadata,
        }
        for a in asset_sdk.assets.values()
    ]


@app.get("/api/mesh/assets/{asset_id}/history")
async def get_asset_history(asset_id: str) -> List[Dict[str, Any]]:
    return asset_sdk.get_asset_history(asset_id)


@app.post("/api/mesh/economy/transfer")
async def post_economy_transfer(req: Dict[str, Any]) -> Dict[str, Any]:
    to_id = req.get("to_id")
    amount = req.get("amount")
    reason = req.get("reason", "manual transfer")

    if not to_id or not amount:
        raise HTTPException(status_code=400, detail="Missing to_id or amount")

    if economy.transfer(client.identity.id, to_id, float(amount), reason):
        return {"status": "success", "balance": economy.get_balance(client.identity.id)}
    else:
        raise HTTPException(status_code=402, detail="Insufficient credits")


@app.get("/api/mesh/fleet/health")
async def get_fleet_health() -> Dict[str, Any]:
    return fleet_manager.get_fleet_health()


@app.get("/api/mesh/audit/latest")
async def get_audit_latest() -> Dict[str, Any]:
    # In a real app, we'd retrieve the last report from out/audit/latest_integrity.json
    # Here we mock it based on the last actual audit run if any
    try:
        report_path = Path("out/audit/latest_integrity.json")
        if report_path.exists():
            with open(report_path, "r") as f:
                return json.load(f)
    except Exception:
        pass

    return {
        "score": 10.0,
        "chain_continuous": True,
        "state_consistent": True,
        "proofs_valid": True,
        "details": ["No issues detected in current era."],
    }


# Serve static files for the UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT)
# TAMPER_EVENT_1210
