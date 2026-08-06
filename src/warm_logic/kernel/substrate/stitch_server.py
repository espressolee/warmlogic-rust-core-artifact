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
Stitch Server
A lightweight, high-integrity telemetry gateway.
Uses Server-Sent Events (SSE) to stream kernel state to the Sovereign Cockpit.
"""

import json
import logging
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("StitchServer")

# Global event queue for subscribers
_event_queue: queue.Queue[Any] = queue.Queue()
_subscribers: List[queue.Queue[Any]] = []
_sub_lock = threading.Lock()
_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}  # {path: callback}
_handler_lock = threading.Lock()

# SSE Re-sync Buffer
_event_buffer: List[Tuple[int, str, Dict[str, Any]]] = (
    []
)  # List of (id, event_type, data)
_buffer_size = 100
_buffer_lock = threading.Lock()
_next_event_id = 1

# Path to the interface directory
INTERFACE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "interface")


class StitchRequestHandler(BaseHTTPRequestHandler):
    """
    Handles SSE connections and static assets for the Stitch Protocol.
    """

    def do_GET(self) -> None:
        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Handle Re-sync via Last-Event-ID
            last_id = self.headers.get("Last-Event-ID")
            if last_id:
                try:
                    last_id_int = int(last_id)
                    with _buffer_lock:
                        # Replay events from buffer starting after last_id
                        for eid, etype, edata in _event_buffer:
                            if eid > last_id_int:
                                msg = {
                                    "event_id": eid,
                                    "event_type": etype,
                                    "data": edata,
                                }
                                self.wfile.write(
                                    f"id: {eid}\ndata: {json.dumps(msg)}\n\n".encode(
                                        "utf-8"
                                    )
                                )
                    self.wfile.flush()
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid Last-Event-ID '{last_id}': {e}")

            # Register subscriber
            sub_q: queue.Queue[Any] = queue.Queue(
                maxsize=100
            )  # Bounded queue for WAN stability
            with _sub_lock:
                _subscribers.append(sub_q)

            logger.info(
                f"🧶 New Stitch Subscriber connected: {self.client_address} (Last-ID: {last_id})"
            )

            try:
                # Use a timeout on sub_q.get to allow checking exit conditions
                while True:
                    try:
                        event = sub_q.get(timeout=0.5)
                        if event is None:
                            break  # Shutdown signal

                        eid = event.get("event_id", "0")
                        data = json.dumps(event)
                        self.wfile.write(f"id: {eid}\ndata: {data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Periodically check if we should still be running?
                        # But we rely on the None signal mostly.
                        # However, let's just loop back.
                        continue
            except (ConnectionResetError, BrokenPipeError):
                logger.info(f"Stitch Subscriber disconnected: {self.client_address}")
            finally:
                with _sub_lock:
                    if sub_q in _subscribers:
                        _subscribers.remove(sub_q)
        elif self.path == "/" or self.path == "/cockpit":
            # Serve the Cockpit UI
            cockpit_path = os.path.join(INTERFACE_DIR, "cockpit.html")
            try:
                with open(cockpit_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                logger.error(f"Failed to serve cockpit.html: {e}")
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        """Processes incoming data from peers (Blocks/Votes)."""
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)

        try:
            # Kinetic Identity Verification (W-ID)
            # All write operations (POST) must be signed.
            from warm_logic.kernel.identity.kinetic_id import KineticIdentity

            pub_key = self.headers.get("X-Warm-ID")
            signature = self.headers.get("X-Warm-Sig")

            if not pub_key or not signature:
                logger.warning(
                    f"⛔ Rejected unsigned request from {self.client_address}"
                )
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error": "Missing W-ID Headers"}')
                return

            # Verify signature over the RAW body bytes logic (decoded as string because the Rust extension expects string)
            # In production we should sign bytes, but the Rust Core takes &str.
            # So we decode utf-8.
            body_str = post_data.decode("utf-8")

            if not KineticIdentity.verify_intent(pub_key, body_str, signature):
                logger.warning(f"Invalid W-ID Signature from {self.client_address}")
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid Kinetic Proof"}')
                return

            payload = json.loads(body_str)

            with _handler_lock:
                handler = _handlers.get(self.path)

            if handler:
                handler(payload)
                self.send_response(202)  # Accepted
                self.end_headers()
                self.wfile.write(b'{"status": "accepted"}')
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(
                    b'{"status": "not_found", "reason": "no handler registered"}'
                )

        except Exception as e:
            logger.error(f"Stitch POST error: '{e}'")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


class StitchServer:
    """
    The Stitch Protocol Gateway.
    """

    _instance = None
    _server_thread = None
    _httpd = None

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """
        Configurable via environment for WAN deployment.
        """
        self.host = host or os.environ.get("STITCH_HOST", "0.0.0.0")
        self.port = (
            port if port is not None else int(os.environ.get("STITCH_PORT", "8033"))
        )
        self.running = False

    @classmethod
    def reset(cls) -> None:
        """
        Hard reset of the protocol state for isolation.
        Stops existing instance and clears handlers, subscribers, and event buffer.
        """
        if cls._instance:
            cls._instance.stop()

        with _handler_lock:
            _handlers.clear()
        with _sub_lock:
            for q in _subscribers:
                try:
                    q.put_nowait(None)
                except Exception:
                    pass
            _subscribers.clear()
        with _buffer_lock:
            _event_buffer.clear()
        cls._instance = None
        cls._server_thread = None
        cls._httpd = None
        logger.info("Stitch Protocol state reset completed.")

    def __new__(cls, *args: Any, **kwargs: Any) -> "StitchServer":
        if cls._instance is None:
            # Type safe singleton pattern
            cls._instance = super(StitchServer, cls).__new__(cls)
        return cls._instance

    def start(self) -> None:
        """Starts the Stitch Server in a background thread."""
        if self.running:
            return

        startup_complete = threading.Event()
        bind_succeeded = {"ok": False}

        def run_server() -> None:
            # Allow reuse address to prevent "Address already in use" during restarts
            HTTPServer.allow_reuse_address = True

            # Retry logic for port binding? With port 0 we don't need retry usually.
            # But let's keep the structure simple:
            self._httpd = None
            try:
                self._httpd = HTTPServer((self.host, self.port), StitchRequestHandler)
                # Update port if it was 0 (dynamic)
                self.port = self._httpd.server_address[1]
                bind_succeeded["ok"] = True
            except OSError as e:
                self._httpd = None
                logger.error(f"Failed to bind Stitch Server: {e}")
                startup_complete.set()
                return

            logger.info(
                f"🧶 Stitch Protocol active at http://{self.host}:{self.port}/stream"
            )
            startup_complete.set()
            try:
                self._httpd.serve_forever()
            finally:
                self.running = False

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()
        startup_complete.wait(timeout=1.0)
        self.running = bind_succeeded["ok"]

    def stop(self) -> None:
        """Stops the Stitch Server."""
        # Signal all subscribers to exit their loops
        with _sub_lock:
            for q in _subscribers:
                try:
                    q.put_nowait(None)
                except Exception:
                    pass
            _subscribers.clear()

        if self._httpd:
            t = threading.Thread(target=self._httpd.shutdown, daemon=True)
            t.start()
            t.join(timeout=2)
            if t.is_alive():
                logger.warning("Stitch Server: HTTPD shutdown timed out.")
            self._httpd.server_close()
        if self._server_thread:
            self._server_thread.join(timeout=2)
        self.running = False
        logger.info("Stitch Server stopped.")

    @staticmethod
    def broadcast(event_type: str, data: Dict[str, Any]) -> None:
        """Broadcasts an event to all connected Stitch subscribers."""
        global _next_event_id

        with _buffer_lock:
            eid = _next_event_id
            _next_event_id += 1
            event = {"event_id": eid, "event_type": event_type, "data": data}
            _event_buffer.append((eid, event_type, data))
            if len(_event_buffer) > _buffer_size:
                _event_buffer.pop(0)

        with _sub_lock:
            for q in _subscribers:
                try:
                    q.put(event, block=False)
                except queue.Full:
                    # Drop old subscriber if queue is full
                    # Standard strategy: Client will re-sync via Last-Event-ID
                    pass

        if not _subscribers:
            logger.debug(f"Broadcast dropped: No subscribers for {event_type}")

    @staticmethod
    def register_handler(path: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a callback for a specific HTTP POST path."""
        from warm_logic.kernel.substrate.chaos_monkey import ChaosMonkey

        # Apply Chaos Middleware
        chaos_callback = ChaosMonkey.apply_middleware(callback)

        with _handler_lock:
            _handlers[path] = chaos_callback
            logger.info(f"Stitch Handler registered for {path} (Chaos Ready)")
