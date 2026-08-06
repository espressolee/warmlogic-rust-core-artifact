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
import atexit
import logging
import os
import sys
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

# Standard OpenTelemetry Imports
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning(
        "⚠️  OpenTelemetry not installed. Distributed tracing will be disabled."
    )


class TelemetryProvider:
    """
    [Phase 56] Enterprise Observability Provider.
    Configures Trace Providers and Exporters (Console/OTLP).
    Gracefully degrades to No-Op if 'opentelemetry' is not installed.
    """

    _instance: Optional["TelemetryProvider"] = None
    _tracer: Optional[Union["NoOpTracer", Any]] = None  # NoOpTracer or trace.Tracer
    _provider: Optional["TracerProvider"] = None
    _shutdown_registered = False

    def __new__(cls) -> "TelemetryProvider":
        if cls._instance is None:
            cls._instance = super(TelemetryProvider, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        if not OTEL_AVAILABLE:
            self._tracer = NoOpTracer()
            return

        is_pytest_runtime = (
            os.environ.get("PYTEST_CURRENT_TEST") is not None
            or os.environ.get("PYTEST_XDIST_WORKER") is not None
            or os.environ.get("PYTEST_VERSION") is not None
            or "pytest" in sys.modules
        )

        # Configure Resource
        resource = Resource.create(
            {
                "service.name": "warmlogic-sovereign",
                "service.version": "0.1.0",
            }
        )

        # Configure Provider
        provider = TracerProvider(resource=resource)
        self._provider = provider

        # In test workers, avoid console exporter worker threads that can outlive
        # pytest's captured streams and cause shutdown-time logging noise.
        if not is_pytest_runtime:
            # Configure Exporter (Default to Console for now, can add OTLP later)
            # In a real deployment, we would check os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            console_exporter = ConsoleSpanExporter()
            processor = BatchSpanProcessor(console_exporter)
            provider.add_span_processor(processor)

        # Set Global Provider
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer("warmlogic.kernel")
        self._register_shutdown_hook()
        if is_pytest_runtime:
            logger.info(
                "🔭 [Telemetry] OpenTelemetry Initialized (Test Mode, exporter disabled)."
            )
        else:
            logger.info("[Telemetry] OpenTelemetry Initialized (Console Exporter).")

    def _register_shutdown_hook(self) -> None:
        if self._shutdown_registered:
            return

        def _shutdown() -> None:
            if self._provider is None:
                return
            try:
                self._provider.shutdown()
            except Exception:
                logger.debug("Telemetry provider shutdown failed", exc_info=True)

        atexit.register(_shutdown)
        self._shutdown_registered = True

    def get_tracer(self, name: str = "warmlogic.kernel") -> Union["NoOpTracer", Any]:
        if not OTEL_AVAILABLE:
            return NoOpTracer()
        return trace.get_tracer(name)


class NoOpTracer:
    """Dummy Tracer that does nothing when OTel is missing."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> "NoOpSpan":
        return NoOpSpan()


class NoOpSpan:
    """Dummy Span context manager."""

    def __enter__(self) -> "NoOpSpan":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[Any] = None) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass
