# Copyright 2026 espressolee
# SPDX-License-Identifier: Apache-2.0
"""Tests for WarmLogic kernel exceptions."""

import pytest

from warm_logic.kernel.sys.exceptions import (
    WarmLogicError,
    SovereignError,
    ConstitutionalBreach,
    MeshNetworkingError,
    PersistenceError,
    IntegrityError,
    RateLimitExceeded,
)


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_base_exception_inheritance(self):
        """All custom exceptions inherit from WarmLogicError."""
        assert issubclass(SovereignError, WarmLogicError)
        assert issubclass(ConstitutionalBreach, WarmLogicError)
        assert issubclass(MeshNetworkingError, WarmLogicError)
        assert issubclass(PersistenceError, WarmLogicError)
        assert issubclass(IntegrityError, WarmLogicError)
        assert issubclass(RateLimitExceeded, WarmLogicError)

    def test_warmlogic_error_is_exception(self):
        """WarmLogicError inherits from Exception."""
        assert issubclass(WarmLogicError, Exception)

    def test_raise_warmlogic_error(self):
        """Can raise and catch WarmLogicError."""
        with pytest.raises(WarmLogicError):
            raise WarmLogicError("test error")

    def test_raise_sovereign_error(self):
        """Can raise and catch SovereignError."""
        with pytest.raises(SovereignError):
            raise SovereignError("identity verification failed")

    def test_raise_constitutional_breach(self):
        """Can raise and catch ConstitutionalBreach."""
        with pytest.raises(ConstitutionalBreach):
            raise ConstitutionalBreach("tau_ethics below threshold")

    def test_raise_mesh_networking_error(self):
        """Can raise and catch MeshNetworkingError."""
        with pytest.raises(MeshNetworkingError):
            raise MeshNetworkingError("DHT bootstrap failed")

    def test_raise_persistence_error(self):
        """Can raise and catch PersistenceError."""
        with pytest.raises(PersistenceError):
            raise PersistenceError("ledger write failed")

    def test_raise_integrity_error(self):
        """Can raise and catch IntegrityError."""
        with pytest.raises(IntegrityError):
            raise IntegrityError("ZK proof verification failed")

    def test_raise_rate_limit_exceeded(self):
        """Can raise and catch RateLimitExceeded."""
        with pytest.raises(RateLimitExceeded):
            raise RateLimitExceeded("request limit exceeded")

    def test_catch_specific_with_base(self):
        """Can catch specific exceptions with base class."""
        with pytest.raises(WarmLogicError):
            raise SovereignError("caught by base")

    def test_exception_message(self):
        """Exception preserves message."""
        msg = "detailed error message"
        try:
            raise IntegrityError(msg)
        except IntegrityError as e:
            assert str(e) == msg

    def test_exception_args(self):
        """Exception preserves args."""
        try:
            raise PersistenceError("error", 123, {"key": "value"})
        except PersistenceError as e:
            assert e.args == ("error", 123, {"key": "value"})
