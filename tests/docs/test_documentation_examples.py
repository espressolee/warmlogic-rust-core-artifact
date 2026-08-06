"""
Documentation Example Tests

Validates that code examples in documentation actually work.
Run with: pytest tests/docs/ -v
"""

import pytest


class TestSDKExamples:
    """Tests for SDK examples from docs/tutorial/01_quickstart.md"""

    def test_sdk_import(self):
        """Verify SDK can be imported."""
        from warm_logic.sdk import SovereignClient, Decision

        assert SovereignClient is not None
        assert Decision is not None

    def test_sovereign_client_initialization(self):
        """Verify SovereignClient can be instantiated."""
        import warnings

        from warm_logic.sdk import SovereignClient

        # Suppress the experimental warning for test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            client = SovereignClient()

        assert client is not None
        assert client.endpoint == "local"

    def test_sovereign_client_host_port_compat(self):
        """Verify old docs constructor style still works."""
        import warnings

        from warm_logic.sdk import SovereignClient

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            client = SovereignClient(host="localhost", port=8000, timeout=60)

        assert client.endpoint == "http://localhost:8000"
        assert client.timeout_seconds == 60.0

    def test_propose_action_basic(self):
        """Test basic propose_action from quickstart example."""
        import warnings

        from warm_logic.sdk import SovereignClient

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            client = SovereignClient()

        # Example from docs/tutorial/01_quickstart.md
        decision = client.propose_action(
            intent="send_email",
            context={"to": "user@example.com", "subject": "Hello"},
        )

        assert decision.verdict in ("ALLOW", "DENY", "PENDING")
        assert decision.proof_hash is not None
        assert len(decision.proof_hash) == 16  # SHA256 truncated to 16 chars

    def test_decision_properties(self):
        """Test Decision object properties."""
        import warnings

        from warm_logic.sdk import SovereignClient

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            client = SovereignClient()

        decision = client.propose_action(intent="test_action", context={})

        # Test properties
        assert hasattr(decision, "verdict")
        assert hasattr(decision, "reason")
        assert hasattr(decision, "proof_hash")
        assert hasattr(decision, "timestamp")
        assert hasattr(decision, "metadata")
        assert hasattr(decision, "allowed")
        assert hasattr(decision, "denied")

    def test_blocked_intent(self):
        """Test that blocked intents are denied."""
        import warnings

        from warm_logic.sdk import SovereignClient

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            client = SovereignClient()

        # These intents should be blocked by constitution
        for blocked_intent in ["delete_all", "bypass_auth", "disable_logging"]:
            decision = client.propose_action(intent=blocked_intent, context={})
            assert decision.verdict == "DENY", f"{blocked_intent} should be denied"
            assert decision.denied is True

    def test_health_check(self):
        """Test health_check method."""
        import warnings

        from warm_logic.sdk import SovereignClient

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            client = SovereignClient()

        health = client.health_check()

        assert health["status"] == "ok"
        assert health["endpoint"] == "local"
        assert "trl" not in health, "TRL readiness level is not a claim this artifact makes"
        assert "rust_core" in health


class TestCLIImports:
    """Tests for CLI module imports."""

    def test_cli_import(self):
        """Verify CLI module can be imported."""
        from warm_logic.app.cli.sovereign_chat import main

        assert main is not None
        assert callable(main)

    def test_kernel_loop_entrypoint_import(self):
        """Verify wlctl kernel loop module exists."""
        from warm_logic.kernel.kernel_loop import run_kernel_loop

        assert callable(run_kernel_loop)


class TestKernelImports:
    """Tests for kernel module imports."""

    def test_kernel_api_import(self):
        """Verify kernel API can be imported."""
        from warm_logic.kernel.api import ModuleRegistry, compute_mode

        assert ModuleRegistry is not None
        assert compute_mode is not None

    def test_rust_loader_import(self):
        """Verify rust_loader can be imported."""
        from warm_logic.kernel import rust_loader

        assert hasattr(rust_loader, "HAS_RUST_CORE")
