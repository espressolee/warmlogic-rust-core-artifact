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
# ==========================================================
# Module: demo_server.py
# Project: Warm Logic — Demo Harness
# Description: Simplified demo server for presentations.
# ==========================================================
"""Demo Server - Lightweight presentation interface for WarmLogic.

This module provides a simplified web interface for demos:
- No API key required (demo mode only)
- Real-time kernel status
- Governance decision visualization
- LLM request interception demo

WARNING: This server is for demos only. Use cockpit/server.py for production.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from warm_logic.kernel.ops.control import KernelContext, KernelLoop
from warm_logic.kernel.ops.metrics import SystemMetrics

# =============================================================================
# Demo Token Manager (Simplified for Demo)
# =============================================================================


class DemoTokenManager:
    """Simplified token manager for demo purposes."""

    def __init__(self) -> None:
        self.balances: Dict[str, float] = {"demo_user": 1000.0}

    def get_balance(self, user_id: str) -> float:
        return self.balances.get(user_id, 0.0)


# =============================================================================
# Demo State
# =============================================================================


class DemoState:
    """Global demo state container."""

    def __init__(self) -> None:
        self.kernel_ctx = KernelContext()
        self.kernel_loop = KernelLoop(self.kernel_ctx)
        self.metrics = SystemMetrics()
        self.token_manager = DemoTokenManager()
        self.start_time = time.time()
        self.requests_processed = 0
        self.requests_allowed = 0
        self.requests_denied = 0
        self.recent_decisions: List[Dict[str, Any]] = []
        self.max_decisions = 50


_state = DemoState()


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="WarmLogic Demo",
    description="AI governance kernel - Demo Mode",
    version="1.0.0-demo",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HTML Dashboard
# =============================================================================

DEMO_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WarmLogic Demo</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 {
            font-size: 2.8rem;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .header .subtitle {
            color: #888;
            font-size: 1rem;
            margin-bottom: 15px;
        }
        .demo-badge {
            display: inline-block;
            background: linear-gradient(90deg, #ff6b6b, #ffa500);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 30px;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 24px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 10px #00ff88; }
            50% { opacity: 0.5; box-shadow: 0 0 5px #00ff88; }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h3 {
            font-size: 0.85rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }
        .metric {
            font-size: 2.8rem;
            font-weight: bold;
            color: #00d4ff;
        }
        .metric.success { color: #00ff88; }
        .metric.danger { color: #ff6b6b; }
        .metric-label {
            font-size: 0.8rem;
            color: #666;
            margin-top: 5px;
        }
        .test-panel {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }
        .test-panel h3 {
            margin-bottom: 15px;
            color: #00d4ff;
        }
        .test-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-allow {
            background: linear-gradient(90deg, #00ff88, #00cc66);
            color: #000;
        }
        .btn-deny {
            background: linear-gradient(90deg, #ff6b6b, #cc4444);
            color: white;
        }
        .btn:hover { transform: translateY(-2px); }
        .decisions-table {
            width: 100%;
            border-collapse: collapse;
        }
        .decisions-table th, .decisions-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .decisions-table th {
            color: #888;
            font-size: 0.8rem;
            text-transform: uppercase;
        }
        .outcome-allow { color: #00ff88; font-weight: bold; }
        .outcome-deny { color: #ff6b6b; font-weight: bold; }
        .footer {
            text-align: center;
            padding: 30px;
            color: #555;
            font-size: 0.85rem;
        }
        .footer a { color: #00d4ff; text-decoration: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1>WarmLogic</h1>
        <div class="subtitle">AI governance kernel</div>
        <span class="demo-badge">DEMO MODE</span>
    </div>

    <div class="status-bar">
        <div class="status-item">
            <div class="status-dot"></div>
            <span>Kernel: <strong id="kernel-state">Active</strong></span>
        </div>
        <div class="status-item">
            <span>Tick: <strong id="tick-count">0</strong></span>
        </div>
        <div class="status-item">
            <span>Uptime: <strong id="uptime">0s</strong></span>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Requests Processed</h3>
            <div class="metric" id="total-requests">0</div>
            <div class="metric-label">Total governance checks</div>
        </div>
        <div class="card">
            <h3>Allowed</h3>
            <div class="metric success" id="allowed-requests">0</div>
            <div class="metric-label">Governance approved</div>
        </div>
        <div class="card">
            <h3>Denied</h3>
            <div class="metric danger" id="denied-requests">0</div>
            <div class="metric-label">Governance blocked</div>
        </div>
        <div class="card">
            <h3>Approval Rate</h3>
            <div class="metric" id="approval-rate">100%</div>
            <div class="metric-label">Success ratio</div>
        </div>
    </div>

    <div class="test-panel">
        <h3>Test Governance Decisions</h3>
        <div class="test-buttons">
            <button class="btn btn-allow" onclick="testRequest('safe')">
                Send Safe Request
            </button>
            <button class="btn btn-deny" onclick="testRequest('risky')">
                Send Risky Request
            </button>
            <button class="btn btn-allow" onclick="testRequest('llm')">
                Test LLM Request
            </button>
        </div>
    </div>

    <div class="card">
        <h3>Recent Decisions</h3>
        <table class="decisions-table">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Request ID</th>
                    <th>Type</th>
                    <th>Outcome</th>
                    <th>Reason</th>
                </tr>
            </thead>
            <tbody id="decisions-body">
                <tr>
                    <td colspan="5" style="text-align: center; color: #666;">
                        Click a test button to generate decisions...
                    </td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="footer">
        <p>WarmLogic AI governance kernel</p>
        <p>Architecture: Rust Core + Python Governance |
           <a href="/docs">API Docs</a> |
           <a href="/api/status">Status JSON</a>
        </p>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();

                document.getElementById('tick-count').textContent = data.kernel.tick_count;
                document.getElementById('uptime').textContent = Math.floor(data.kernel.uptime_seconds) + 's';
                document.getElementById('total-requests').textContent = data.kernel.requests_processed;
                document.getElementById('allowed-requests').textContent = data.kernel.requests_allowed;
                document.getElementById('denied-requests').textContent = data.kernel.requests_denied;

                const total = data.kernel.requests_processed || 1;
                const rate = ((data.kernel.requests_allowed / total) * 100).toFixed(1);
                document.getElementById('approval-rate').textContent = rate + '%';

                if (data.decisions && data.decisions.length > 0) {
                    const tbody = document.getElementById('decisions-body');
                    tbody.innerHTML = data.decisions.map(d => `
                        <tr>
                            <td>${new Date(d.timestamp).toLocaleTimeString()}</td>
                            <td style="font-family: monospace; font-size: 0.85rem;">${d.request_id}</td>
                            <td>${d.request_type}</td>
                            <td class="outcome-${d.outcome}">${d.outcome.toUpperCase()}</td>
                            <td>${d.reason}</td>
                        </tr>
                    `).join('');
                }
            } catch (e) {
                console.error('Status fetch failed:', e);
            }
        }

        async function testRequest(type) {
            try {
                const resp = await fetch('/api/test/' + type, { method: 'POST' });
                const data = await resp.json();
                console.log('Test result:', data);
                fetchStatus();
            } catch (e) {
                console.error('Test request failed:', e);
            }
        }

        fetchStatus();
        setInterval(fetchStatus, 2000);
    </script>
</body>
</html>
"""


# =============================================================================
# Request Models
# =============================================================================


class LLMRequest(BaseModel):
    """Simulated LLM API request."""

    model: str = "gpt-4"
    messages: List[Dict[str, str]] = []
    temperature: float = 0.7


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Demo dashboard."""
    return DEMO_HTML


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """Get current system status."""
    uptime = time.time() - _state.start_time

    return {
        "kernel": {
            "state": "running",
            "tick_count": _state.kernel_ctx.tick_count,
            "uptime_seconds": uptime,
            "requests_processed": _state.requests_processed,
            "requests_allowed": _state.requests_allowed,
            "requests_denied": _state.requests_denied,
        },
        "decisions": _state.recent_decisions[-20:],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/health")
async def health() -> Dict[str, str]:
    """Health check."""
    return {"status": "healthy", "mode": "demo"}


@app.post("/api/test/{request_type}")
async def test_request(request_type: str) -> Dict[str, Any]:
    """Generate a test governance request."""
    request_id = f"DEMO-{uuid.uuid4().hex[:8].upper()}"

    # Simulate governance decision
    if request_type == "risky":
        outcome = "deny"
        reason = "Security violation detected (demo)"
    elif request_type == "llm":
        outcome = "allow"
        reason = "LLM request approved by governance"
    else:
        outcome = "allow"
        reason = "Standard request approved"

    # Update state
    _state.requests_processed += 1
    if outcome == "allow":
        _state.requests_allowed += 1
    else:
        _state.requests_denied += 1

    # Tick the kernel
    _state.kernel_loop.tick({"epsilon_c": 0.95, "tau_ethics": 0.1})

    # Record decision
    decision = {
        "request_id": request_id,
        "request_type": request_type,
        "outcome": outcome,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _state.recent_decisions.append(decision)
    if len(_state.recent_decisions) > _state.max_decisions:
        _state.recent_decisions.pop(0)

    return decision


@app.post("/v1/chat/completions")
async def llm_proxy(request: LLMRequest) -> Dict[str, Any]:
    """Simulated LLM API proxy with governance."""
    request_id = f"LLM-{uuid.uuid4().hex[:8].upper()}"

    # Governance check
    _state.requests_processed += 1
    _state.requests_allowed += 1
    _state.kernel_loop.tick({"epsilon_c": 0.95, "tau_ethics": 0.1})

    # Record decision
    decision = {
        "request_id": request_id,
        "request_type": "llm_chat",
        "outcome": "allow",
        "reason": "LLM request governed and forwarded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _state.recent_decisions.append(decision)

    # Return simulated response
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"[WarmLogic Governed] Request {request_id} approved. This is a demo response.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "_warmlogic": {
            "governed": True,
            "request_id": request_id,
            "kernel_tick": _state.kernel_ctx.tick_count,
        },
    }


# =============================================================================
# Entry Point
# =============================================================================


def run_demo_server(host: str = "0.0.0.0", port: int = 8888) -> None:
    """Run the demo server."""
    import uvicorn

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║             WarmLogic Sovereign Governance Demo               ║
╠═══════════════════════════════════════════════════════════════╣
║  Dashboard:    http://{host}:{port}
║  API Status:   http://{host}:{port}/api/status
║  LLM Proxy:    http://{host}:{port}/v1/chat/completions
║  API Docs:     http://{host}:{port}/docs
║                                                               ║
║  Mode: DEMO (No API key required)                             ║
║  Kernel: Active | Governance: Enabled                         ║
╚═══════════════════════════════════════════════════════════════╝
""")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_demo_server()
